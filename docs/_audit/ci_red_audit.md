# CI red audit (COMMAND 105)

Read-only audit. Nothing in the repository was changed except this report; nothing was committed. Date: 2026-11-09. HEAD `90f2629`. Every run below was done outside the working tree (virtual environments, temporary worktrees and data directories under the session scratch folder).

## 0. Correction of the previous report

The message that followed the push said that "Unit tests and lint" had been red since 2026-11-04 and that its last green run was `fde58aa`. That was wrong. The workflow was added on 2026-10-27 (`abe5868`, COMMAND 73) and **none of its 26 runs was ever green**: the lint step fails first, so the unit tests have never run in CI. At `fde58aa` the lint already gave 46 errors; it gave 53 at `7f09586` and 54 from `947fae2` on (ruff 0.17.3, then 0.17.4 at HEAD). Only "Synthetic fixture (ZZZ)" has a real last green run (`fde58aa`, 2026-10-30), and its first red run is `7f09586` (2026-11-04). "Regression" is green on every recent push.

## 1. The workflows

| Workflow | Trigger | Job and step | Exact command | Python | Tool versions in the last run |
|---|---|---|---|---|---|
| `unit.yml` | push to main, pull request, manual | `unit`, step "Ruff (lint)" | `ruff check src tests scripts main.py` | 3.11 and 3.12 (matrix, `fail-fast: false`) | ruff 0.17.4 (not pinned: `dev` extra lists `ruff` with no version) |
| `unit.yml` | same | `unit`, step "Unit tests" | `pytest tests/unit -m "not slow" -p no:cacheprovider -q` (2246 of 2248 tests selected) | 3.11 and 3.12 | pytest 9.2.0, numpy 2.5.4 (3.12), pandas 3.1.1, geopandas 1.2.0, shapely 2.2.0, rasterio 1.5.2, scipy 1.18.1, xarray 2026.9.0, matplotlib 3.11.2 |
| `synthetic_fixture.yml` | same | `synthetic-fixture` | `pytest tests/synthetic -m synthetic -v`, then `pytest tests/unit/test_synthetic_value_separation.py tests/unit/test_iso3_literals.py -v` | 3.12 | same resolution |
| `synthetic_fixture.yml` | same | `hand-validation` | `pytest -m synthetic ... test_zzz_end_to_end.py::test_every_phase_from_f1_to_f6_runs_and_succeeds test_zzz2_end_to_end.py::test_every_phase_from_f1_to_f8_runs_and_succeeds`, then `validate_zzz_by_hand.py <run dir> <wind or solar> <zzz or zzz2>` for the four cases | 3.12 | same resolution |
| `regression.yml` | same | `regression` | `pytest tests/regression -m regression -q` | 3.12 | same resolution |

Locally the lint ran with ruff 0.16.8 (58 errors, a different rule set) and Python 3.11.9; to reproduce the CI I used ruff 0.17.4 in a separate environment. **Reproduced: 54 errors, 30 fixable with `--fix`, 13 more with `--unsafe-fixes`, as in the CI log.** The configuration is the same: `[tool.ruff]` of `pyproject.toml` has only `line-length = 100` and `target-version = "py311"`, so the rules checked are ruff's own default set, which changes with the ruff version. Because ruff and every dependency are unpinned, the CI result can change with no change of code.

## 2. The 54 lint errors

By rule:

| Rule | Name | Errors | safe fix | unsafe fix | no fix (manual) |
|---|---|---|---|---|---|
| RUF100 | unused-noqa | 12 | 12 | 0 | 0 |
| RUF046 | unnecessary-cast-to-int | 7 | 3 | 4 | 0 |
| B023 | function-uses-loop-variable | 6 | 0 | 0 | 6 |
| RUF059 | unused-unpacked-variable | 6 | 0 | 4 | 2 |
| I001 | unsorted-imports | 4 | 4 | 0 | 0 |
| UP017 | datetime-timezone-utc | 4 | 4 | 0 | 0 |
| SIM114 | if-with-same-arms | 3 | 3 | 0 | 0 |
| C408 | unnecessary-collection-call | 2 | 0 | 2 | 0 |
| UP033 | lru-cache-with-maxsize-none | 2 | 2 | 0 | 0 |
| F401 | unused-import | 1 | 1 | 0 | 0 |
| F811 | redefined-while-unused | 1 | 0 | 0 | 1 |
| F821 | undefined-name | 1 | 0 | 0 | 1 |
| F841 | unused-variable | 1 | 0 | 1 | 0 |
| PERF102 | incorrect-dict-iterator | 1 | 0 | 1 | 0 |
| PYI034 | non-self-return-type | 1 | 0 | 1 | 0 |
| S112 | try-except-continue | 1 | 0 | 0 | 1 |
| UP037 | quoted-annotation | 1 | 1 | 0 | 0 |
| **total** | | **54** | **30** | **13** | **11** |

By file (25 files):

| File | Errors | Rules (count) | Fix class (count) |
|---|---|---|---|
| `scripts/affected_tests.py` | 7 | RUF100 (1), S112 (1), SIM114 (3), UP033 (2) | none 1, safe 6 |
| `scripts/check_manifests.py` | 2 | RUF100 (2) | safe 2 |
| `scripts/profiling/bench_guard.py` | 1 | RUF100 (1) | safe 1 |
| `scripts/profiling/measure_layer_memory.py` | 1 | I001 (1) | safe 1 |
| `scripts/profiling/parse_logs.py` | 1 | RUF100 (1) | safe 1 |
| `scripts/proofs/diagnose_clip_shortcut.py` | 3 | RUF046 (2), UP037 (1) | safe 3 |
| `scripts/report_road_distance.py` | 1 | RUF046 (1) | safe 1 |
| `scripts/unattended_check.py` | 2 | RUF100 (1), UP017 (1) | safe 2 |
| `src/geofrea/core/deferred_check.py` | 1 | UP017 (1) | safe 1 |
| `src/geofrea/core/layer_process.py` | 2 | RUF100 (2) | safe 2 |
| `src/geofrea/core/raster_io.py` | 1 | PYI034 (1) | unsafe 1 |
| `src/geofrea/core/reference_store.py` | 2 | UP017 (2) | safe 2 |
| `src/geofrea/land_eligibility/cells.py` | 6 | B023 (6) | none 6 |
| `src/geofrea/technical_potential/cf_table.py` | 2 | RUF046 (2) | unsafe 2 |
| `tests/synthetic/test_deferred_check_zzz.py` | 1 | RUF059 (1) | unsafe 1 |
| `tests/unit/test_adopt_aligned_cache_keys.py` | 2 | RUF059 (2) | none 2 |
| `tests/unit/test_cf_table.py` | 3 | F401 (1), F811 (1), I001 (1) | none 1, safe 2 |
| `tests/unit/test_core_memory_guard.py` | 2 | I001 (1), RUF100 (1) | safe 2 |
| `tests/unit/test_equivalence_and_clipped_cache.py` | 2 | RUF046 (2) | unsafe 2 |
| `tests/unit/test_land_eligibility_cells.py` | 3 | F821 (1), I001 (1), RUF100 (1) | none 1, safe 2 |
| `tests/unit/test_lcoe_kernel.py` | 1 | C408 (1) | unsafe 1 |
| `tests/unit/test_orchestrator.py` | 2 | C408 (1), F841 (1) | unsafe 2 |
| `tests/unit/test_orchestrator_manifest_write.py` | 2 | RUF100 (2) | safe 2 |
| `tests/unit/test_raster_inspection.py` | 3 | RUF059 (3) | unsafe 3 |
| `tests/unit/test_unattended_check.py` | 1 | PERF102 (1) | unsafe 1 |

By area: `src` 14 errors in 6 files, `scripts` 18 in 8 files, `tests` 22 in 11 files, `main.py` 0.

Two of the manual ones are not style: `tests/unit/test_land_eligibility_cells.py:185` F821 uses `rasterio.Affine` in an annotation of a test helper without importing `rasterio` (harmless at run time because the annotation is not evaluated, but the name is undefined), and `tests/unit/test_cf_table.py:133` F811 is the usual pytest pattern of importing a fixture and naming a parameter after it (a false positive; the fix is a noqa or an alias). The six B023 in `src/geofrea/land_eligibility/cells.py:233-235` are a closure `block_sum` defined inside the stripe loop that reads `c0`, `c1`, `g0`, `g1`, `lat0`; it is called in the same iteration, so the late-binding hazard B023 warns about does not occur (false positive).

## 3. What `ruff --fix` would change (`--diff`, nothing applied)

Method: `ruff check --fix --diff` and `--fix --unsafe-fixes --diff` with 0.17.4 on the tree; then the same fixes applied to copies of `src` (outside the repository) and compared, file by file, with the normalised syntax tree the fingerprint uses (`core/code_fingerprint.py`: docstrings, comments and formatting are not in it) and with `closure_fingerprint` of the 19 phases and `function_fingerprint` of the 13 cache entries (`core/cache_code.py`). Scripts and tests are not part of any closure (no `src` module imports them).

| File | Fix class | In a fingerprinted closure? | Changes the syntax tree of a function? | Fingerprints changed |
|---|---|---|---|---|
| `src/geofrea/core/layer_process.py` (RUF100 x2) | safe | yes (infrastructure of the layers) | **no**: tree identical (only `noqa` comments) | none |
| `src/geofrea/core/deferred_check.py` (UP017) | safe | infrastructure module, outside every phase closure | yes: `_now` (`timezone.utc` to `datetime.UTC`) and the import | none (0 of 19 phases, 0 of 13 cache entries) |
| `src/geofrea/core/reference_store.py` (UP017 x2) | safe | same | yes: `_now`, `ReferenceStore` (one method) and the import | none |
| `src/geofrea/core/raster_io.py` (PYI034) | **unsafe** | yes | yes: `RasterStream.__enter__` return annotation becomes `Self`, import added | 9 phases (`grid_alignment`, `siting_layers`, `land_eligibility`, `lcoe_modeling`, `lcoe_maps`, `potential_maps`, `robustness_analysis`, `robustness_maps`, `external_validation`) and 2 cache entries (`aligned_layer.glo30`, `aligned_layer.fabdem_slope`) |
| `src/geofrea/technical_potential/cf_table.py` (RUF046 x2) | **unsafe** | yes | yes: `_grids` (`int(round(x))` to `round(x)`; same integer for a float, so no change of result expected, but the tree changes) | 5 phases (`technical_potential`, `potential_maps`, `lcoe_modeling`, `robustness_analysis`, `sample_size_convergence`) |
| `src/geofrea/land_eligibility/cells.py` (B023 x6) | no fix (manual) | yes | a manual rewrite would change the tree of `aggregate_to_cells`; a `# noqa: B023` would not | `land_eligibility` and what follows it, if rewritten |
| 8 files in `scripts/` (RUF100, I001, UP033, UP017, UP037, RUF046, SIM114; S112 of `affected_tests.py` has no fix) | safe | no | not applicable to the pipeline | none |
| 4 files in `tests/` (RUF100, I001, F401) | safe | no | not applicable | none |
| 7 files in `tests/` (RUF059, RUF046, C408, F841, PERF102, F811, F821) | unsafe or manual | no | not applicable | none |

Result: **the 30 safe fixes change no fingerprint** (0 of 19 phases, 0 of 13 cache entries; two infrastructure files change their tree but belong to no closure). Applying the 13 unsafe fixes would change the code fingerprint of 11 phases and 2 internal caches (the F2a elevation and slope layers), so the next run would treat F2a, F2b, F3, F5, F6 and F7 as changed code and recompute them, although the results are expected equal. The unsafe fixes of `src` and the six B023 are therefore not "formatting": the safe way to clear them without touching a fingerprint is a `noqa` comment or a per-file ignore, which is the author's choice (open decision 1).

## 4. Hand validation of ZZZ and ZZZ2: the failing checks

I ran the CI commands locally (the two end-to-end tests, then the validator for the four cases) on the same code as HEAD. The result is the CI result: **ZZZ wind 34 of 42, ZZZ solar 39 of 40, ZZZ2 wind 42 of 42 and ZZZ2 solar 40 of 40 checks pass**; the failures are in ZZZ only, 9 rows in all. They reproduce with pandas 2.3.3 locally and pandas 3.1.1 in CI, so they do not depend on the dependency versions.

| Case | Check | Obtained | Expected (by hand) | Difference | Tolerance |
|---|---|---|---|---|---|
| ZZZ wind | F7 nominal top-5 cells | 13655203, 13662402, 13662403 | 13655203, 13662402, 13662403, 13669602, 13669603 | 1 | 0 |
| ZZZ wind | F7 robust top-5 cells | same three | same five | 1 | 0 |
| ZZZ wind | H1 reference p_k^2 | 0.07438016529 | 0.08650519031 | 0.0121 | 1e-12 |
| ZZZ wind | H2 O (share of T selected by both procedures) | 0.3333333333 | 0.3421149659 | 0.00878 | 1e-12 |
| ZZZ wind | H2 O_ref = T / Q_max | 0.2692284775 | 0.2940831219 | 0.0249 | 1e-12 |
| ZZZ wind | H5 E_0 (TWh/year at m0) | 5.567199136 | 8.154370686 | 2.59 | 1e-9 |
| ZZZ wind | H5 Delta E | 0.4906544825 | 0.7186699148 | 0.228 | 1e-9 |
| ZZZ wind | H5 R_loss | 0.0881386209 | 0.08813686715 | 1.75e-6 | 1e-9 |
| ZZZ solar | F3 cell 13669600: `dist_sub_km` | 15.97778326 | 15.33035008 | 0.647 | 0.01 |

(The ZZZ2 solar world prints `EXPECTED {"v_f_cases": 205, ...}`; that line is information, not a failed check: the 205 cases of OQ-071 are the observed PRIM set, which the test pins.)

### First failing commit

The CI runs only on pushes to `main`, so I bisected locally in temporary worktrees outside the repository (the ZZZ end-to-end test plus the validator of that commit, as the workflow does), starting from the CI counts per push (`40/38/40/38` at `fde58aa`).

| Failure | Last commit that passes | First commit that fails | Message |
|---|---|---|---|
| ZZZ wind, 8 rows | `a9dd561` (42 of 42; also `be7e26c` in CI) | **`649b070`** | "COMMAND 96: OQ-069 resolved (rule A in F7, common-ensemble sensitivity), optional_produces, pinned expected entries" |
| ZZZ solar, `dist_sub_km` | no earlier commit has the check | **`b96d0ee`** (the commit that adds the check; also red at HEAD) | "COMMAND 84: OSM substation fetch and per-country counts, pv_hot_zone_degradation shares, V-01 refreeze (poi layers), ZZZ2 world and hand validator re-derived" |

Note on the solar row: at `9f5f01f`, the commit before `b96d0ee`, the validator of that commit crashes (`KeyError: 'grid_cost_usd_per_mw_km'`, for both technologies), so the hand validation was already red from the Group 3 code until `b96d0ee` re-derived it; the commits `ea83fd2` to `130cde8` were not run one by one. CI's first red push for this workflow is the merge `7f09586`, which contains all of them.

### Classification

| Failing check | Class | Basis |
|---|---|---|
| ZZZ wind, the 8 rows | **(a) expectation out of date because of a deliberate change** | F7 rule A (D-F7-064, OQ-069 resolved 2026-11-04, METHODOLOGY 16.3.0, D-F5-041): a cell flagged `incomplete_ensemble` leaves the F7 set. In the ZZZ run the F5 file `ensemble_wind__central.parquet` flags 6 cells (13669600 to 13669605) with 30 of 31 members; two of them (13669602, 13669603) are exactly the two cells the hand validator expects in the top 5 and the pipeline no longer ranks, so the obtained top 5 is the expected one minus those two. The validator (last changed in `b96d0ee`) has no notion of the rule. The test of the commit (`tests/synthetic/test_zzz_end_to_end.py`) was updated to expect `incomplete_ensemble`; the validator was not. OQ-071 is not the cause (it concerns the PRIM box of ZZZ2 solar, which passes), and neither are D-F3-0xx, D-F2a-0xx or the Group 6 rules (the ZZZ wind result was 42 of 42 after them, at `a9dd561`). `R_loss` differs by only 1.75e-6 but against a tolerance of 1e-9; it belongs to the same domain change by construction (H5 uses the F7 set), but I did not prove that separately. |
| ZZZ solar `dist_sub_km` | **open: (c) defect of the expectation, or (b) a defect of the layer** (decision 2) | The validator computes the mean haversine distance from the exact point of the substation (20.16, -4.90) to the pixels of the cell, tolerance 0.01 km. The POI layer rasterises the point into one pixel whose centre is (20.165, -4.895), 0.005 degree away on each axis (about 0.78 km), and measures from there (`calculate_wgs84_isotropic_distance` over a distance transform of the burnt pixel); the obtained distance is 0.647 km larger. I checked the burnt pixel in the output raster. So the two disagree by the pixel quantisation of the layer, which the check does not model; the label itself says "the run uses the ellipsoid", not "from the pixel centre". The fixture is not at fault (one Point substation, valid). Whether the quantisation is intended is not in the records I read. |

How to derive the new expectation of class (a) without copying the pipeline's value: in `validate_zzz_by_hand.py`, count the members of each cell from the climate inputs with numpy (the members with a valid, unmasked wind factor in the windows the F7 analysis uses, read from the miniature ISIMIP files of the fixture, not from the F5 flag); drop from the F7 set the cells that have fewer members than the technology expects; recompute nominal and robust ranks, `p_k^2`, `O`, `O_ref`, `E_0`, `Delta E` and `R_loss` on the remaining cells with the formulas already in the validator; and add a check that the cells it dropped are the ones F5 flagged. The values that result are the new expectations; none is copied from the run.

## 5. What the unit job runs after the lint, and the risk of red after the lint is fixed

Difference between CI and the local suite:

| Item | CI (`unit.yml`) | Local suite of the author |
|---|---|---|
| Command | `pytest tests/unit -m "not slow" -p no:cacheprovider -q`: 2246 tests | `pytest -q -p no:cacheprovider`: 2379 tests (all of `tests/`, slow ones included) |
| Python | 3.11 and 3.12 | 3.11.9 |
| OS | Ubuntu | Windows 10 |
| Dependencies | the newest allowed by `pyproject.toml`: pandas 3.1.1, geopandas 1.2.0, shapely 2.2.0, matplotlib 3.11.2, numpy 2.5.4, pytest 9.2.0 | pandas 2.3.3, geopandas 1.1.2, shapely 2.1.2, matplotlib 3.10.8, numpy 2.4.6, pytest 9.0.2, xarray 2025.12.0 (older than the `>=2026.7.0` the project asks for) |
| Extra packages | none | Cartopy 0.25.0, scikit-image, scikit-learn and others that the project does not declare |

Measured here (the local run of the CI command passes: **2246 passed, 2 deselected**), then the same command in a clean environment built from the CI dependency list (Python 3.11, Windows, so Linux itself is not covered):

- With the CI versions, **55 tests fail**: 18 + 18 in `test_mapstyle_panels.py` (overlap and cut-off checks of the sheets), 13 in `test_mapstyle_archetypes.py`, 3 in `test_mapstyle.py`, 1 in `test_mapstyle_classed.py`, and 1 in `test_results_synthesis.py` that was an artefact of my environment (it runs `python -I` and needs the package installed; it passes once installed).
- I isolated the cause by changing one package at a time on the four `test_mapstyle*` files (157 tests): **geopandas 1.2.0 is the cause of 52 failures** (with geopandas 1.1.2 all 157 pass, with pandas 3.1.1 and shapely 2.2.0 and matplotlib 3.10.8; matplotlib 3.11.2 was only tried together with geopandas 1.2.0); **Pillow 13.0.0** (the CI takes the newest) changes the perceptual hashes of the golden images and breaks at least one more test (`test_synthetic_maps_match_their_baseline`), which passes with Pillow 12.1.0. pandas 3.1.1 and shapely 2.2.0 break nothing in this group.
- The rest of the unit tests passed in the CI-version environment (2195 of 2246 with Pillow 12.1.0, the 51 failures all in the figure tests above).

So the answer to "is there a risk that the suite fails in CI once the lint is fixed" is **yes, measured: the lint is not the only red**. With the lint clean, `Unit tests and lint` would still fail on the figure tests as long as ruff, geopandas and Pillow are unpinned; on Ubuntu, with other fonts and a different text rendering, further figure and golden-image tests may fail as well, which I could not measure here. The same unpinned resolution applies to the synthetic and regression workflows (they are green or fail for the reasons in section 4, not because of versions: the hand-validation failures reproduce locally).

## 6. Proposed line for CLAUDE.md (not applied)

> Before every commit or push, read the state of the CI on `main` with `gh run list --branch main --limit 6` and report to the author the conclusion of each workflow for the current HEAD and the last green commit of each; a red workflow is never carried silently: say which commit turned it red, and after each push wait for the workflows of the new HEAD and report them before the next command.

## 7. Open decisions, awaiting the author (none decided or applied)

1. **Lint.** How to get `Unit tests and lint` green: (i) apply the 30 safe fixes (no fingerprint changes) and clear the other 24 with `noqa` comments or a per-file ignore in `pyproject.toml`, which changes no fingerprint; (ii) also apply the unsafe fixes of `raster_io.py` and `cf_table.py` and rewrite the six B023, which changes the code fingerprint of 11 phases and 2 caches and needs the equivalence proof and a recompute (section 3); (iii) pin ruff to a version so the rule set stops moving.
2. **`dist_sub_km` of ZZZ solar.** Whether the layer should measure from the exact point of the substation (a change of code and of results, MAJOR) or the validator should model the pixel of the layer (tolerance about half a pixel diagonal, 0.78 km at this latitude). Class (b) or (c); not decided.
3. **ZZZ wind validator.** Authorise the re-derivation of the F7 rows by the procedure of section 4 (class (a), no change of pipeline code; the validator is the file of the audit `docs/_audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py`).
4. **Pinning the dependencies of the CI** (at least geopandas below 1.2, Pillow below 13, ruff) or updating the goldens and the layout tests to the new versions; and whether the CI should also run the 131 tests of `tests/` that the unit job leaves out. A decision on the figure tests needs a look at the images, not only at the hash.
5. **Linux.** The figure and golden tests have only been run on Windows. Whether to run the unit job once on a Linux machine or on the CI itself with the versions pinned before declaring it green.

No code, configuration or fixture was changed. `git status` shows this report and nothing else.

## 8. Execution of COMMAND 106 (lint to zero, CI pins, two checking rules; 2026-11-09, not committed)

Author's verdict applied: lint by option (i) plus (iii): safe fixes, manual correction in `scripts/` and `tests/`, `noqa` with a reason in `src`, ruff pinned; no fingerprint touched.

**Result.** `ruff check src tests scripts main.py` with ruff 0.17.4: `All checks passed!` (0 errors). The full suite was not run here (COMMAND 109).

**Fingerprints.** `closure_fingerprint` of the 19 phases and `function_fingerprint` of the 13 caches were written to a file outside the repository before the first edit and again after the last one: the two files are byte-identical (`cmp`). The edits in `src` are:

| file | change | rule |
|---|---|---|
| `core/deferred_check.py`, `core/reference_store.py` | `timezone.utc` to `UTC` (the fix of ruff, 2 files, 3 lines) | UP017 |
| `core/layer_process.py` | 2 `# noqa: S301` comments removed, the rule is not enabled | RUF100 |
| `core/raster_io.py` | `# noqa: PYI034` on `RasterStream.__enter__` | PYI034 |
| `technical_potential/cf_table.py` | `# noqa: RUF046` on the 2 lines of `_grids` | RUF046 x2 |
| `land_eligibility/cells.py` | `# noqa: B023` on the 2 lines that use the loop names (6 findings) | B023 x6 |

Nine suppressions in `src` (1 + 2 + 6), recorded as OQ-073. The `UTC` change alters the AST of the two `_now` functions, but both modules are outside the closure of every phase, which the unchanged fingerprints confirm.

**Manual corrections (scripts and tests).** The 30 safe fixes plus: C408 x2 (`dict(...)` to a literal), F841 (unused `call_log`), RUF059 x5 (underscore prefix), RUF046 x2 (`int(round(x))` to `round(x)` in a test), PERF102 (`.values()`), F821 (`import rasterio` in `test_land_eligibility_cells.py`; the annotation needs the name), S112 in `scripts/affected_tests.py` (`contextlib.suppress(Exception)` in place of try/except/continue: same behaviour, the loop body is the last statement). One safe fix was wrong and was reverted by hand: ruff removed the imported fixture `world` from `tests/unit/test_cf_table.py` (F811 on the argument of the test that uses it); the import was restored with `# noqa: F401` and the argument carries `# noqa: F811`, both with the reason (pytest fixture pattern). The safe fixes also removed `noqa` comments and file-level `# ruff: noqa` lines that ruff 0.17.4 reports as unused (RUF100) and collapsed one if/elif chain of `scripts/affected_tests.py` into one condition with the same logic.

**CI.** `ci/constraints.txt` (ruff 0.17.4, geopandas 1.1.2, Pillow 12.1.0, matplotlib 3.10.8) is used as `pip install -c ci/constraints.txt -e ".[dev]"` in the four install steps of the three workflows; nothing else pinned, `pyproject.toml` unchanged. `pip install --dry-run` with the file resolves.

**Records.** OQ-073 (the 9 suppressions), OQ-074 (geopandas 1.2.0, 52 figure tests), OQ-075 (Pillow 13, golden hashes) in `docs/OPEN_QUESTIONS.md`; two rules added to the Commits section of `CLAUDE.md` (the line of section 6 and the local run of the two end-to-end tests and the hand validator before a commit that changes `src`).

**Still red after this command (not touched).** The ZZZ wind rows (class a) and ZZZ solar `dist_sub_km` (b or c) of the Synthetic fixture workflow remain open decisions of the author; the Unit workflow is expected to reach its tests for the first time and has not been run on Linux.
