# Cleanup 82: organization of GeoFREA, GeoFREA_data and the sibling folders

COMMAND 82, 2026-10-30. Rules applied (no verdicts asked): **delete** only what has no reader in code, manifest, config or test **and** is regenerable or a duplicate; **quarantine** (to `D:\Douglas\DOUTORADO\_quarantine_20261030\`, same relative path, `restore_quarantine.ps1` puts everything back) what looks unnecessary but is not provably so;
**reorganize** what is only structure, updating every reference. Nothing under `D:\Douglas\DOUTORADO\database` was written, and no country was run. Companion files: `_quarantine_20261030\INDEX.md`, `docs/PIPELINE_GUIDE.md`, `docs/_audit/optimization_gain_82.md`.

## 0. Pending items

| Item | State found | Action |
|---|---|---|
| tag `adopt-base-75` on `428adec` | exists (annotated; the commit it points to is `428adec6a974...`) | none |
| `perf/75-performance` replaced by the tag in `run_unattended.ps1`, `PROGRESS.json`, `core.md` | already done by COMMAND 81 in those three | the remaining mentions were in `performance_75.md` (the adoption command line) and the `-Worktree` help of `run_unattended.ps1`: corrected |
| delete `feat/wind-cf-pixel` if merged | the branch does not exist (local or remote) | none |
| branches left | `main`, `backup-before-split`, `feat/cache-restamp` (not merged into `main`, kept) | none |

## 1. Sibling folders of `D:\Douglas\DOUTORADO`

| Folder | Size, files, newest file | Referenced by code, manifests or config? | Action |
|---|---|---|---|
| `database` | not measured | read-only shared raw (`GEOFREA_SHARED_RAW_DIR`) | **untouched** |
| `GeoFREA` | the repository | | section 2 |
| `GeoFREA_data` | raw 105 GB; interim 2.8 GB; outputs 4.6 GB | `GEOFREA_DATA_DIR` | section 3 |
| `GeoFREA_data_profile76` | 240 MB, 335 files, 2026-10-29 | no (its `raw` is a link to `GeoFREA_data/raw`; only the profile document names the worktree) | **quarantine** (a rename; the link was not followed) |
| `docs_backup` | 0.5 MB, 46 files, 2026-09-15 | no | **quarantine** |
| `geoworld_framework` | 5.0 GB, 20,311 files, 2026-09-16 | yes: `GEOWORLD_BASELINE_DIR` in `.env`, METHODOLOGY, `settings.yaml` (read-only consult) | keep |
| `shared-data-sources` | 26 MB, 17 files, 2026-10-15 | no by design: its README says it is a copy-from folder for the articles A1 to A3, not a live dependency | keep |
| `other` | 11 files, 2026-10-14 (hypothesis `.tex`, notes, playbook) | no (thesis writing material) | keep |
| `GeoFREA_execution_playbook_v2_active.md`, `v3_active.md`, `GEOFREA_figuras_spec_claude_code.md` | root files | `figuras_spec` is cited by `scripts/audit_potential.py` and the F5 record; the playbooks by `2026-10_F6_design.md` | keep |

`.env` points `GEOFREA_LEGACY_BASELINE_DIR` at `GeoFREA_data\reference\legacy_baseline_fc7b43d`, which does not exist (the regression tests use the in-repo fixtures of `tests/fixtures`). The variable is left as it is; noted here.

## 2. Repository `GeoFREA`

| Path | Finding | Action |
|---|---|---|
| `__pycache__` x 25, `.ruff_cache`, `.pytest_cache` (outside `.venv`) | regenerable, ignored by git | **deleted**, 18.6 MB |
| `logs/` (32 acquisition logs of 2026-09-29 to 2026-10-06, 2.6 MB) | untracked, under the repository root where CLAUDE.md says logs must not be; no reader | **quarantine** `GeoFREA\logs` |
| `scripts/` | 27 scripts and 3 profiling tools. Nine one-shot proofs of COMMANDS 75 to 80 had no reader outside the audit documents (and `adopt_aligned_cache_keys.py` for one) | moved to `scripts/proofs/`: `check_aligned_equivalence`, `check_clip_equivalence`, `check_clip_layers_equivalence`, `check_mainland_equivalence`, `check_polygon_derived_equivalence`, `check_population_strips`, `check_raster_step_equivalence`, `compare_png_dirs`, `diagnose_clip_shortcut` (`REPO` is now `parents[2]`; every textual reference updated; the child processes of the checks start themselves by `__file__`, so they are unaffected) |
| `docs/_audit/*.json` (12 proofs of COMMANDS 75 to 80) | mixed with the dated reports | moved to `docs/_audit/proofs_75_77/`; references updated in `adopt_aligned_cache_keys.py`, `check_aligned_equivalence.py`, `run_unattended.ps1`, `PROGRESS.json`, `performance_75.md`, `optimizations_77.md`, `core.md` |
| `docs/_audit/*.md` (dated and numbered reports) | kept in place on purpose: code comments and `config/experiments.yaml` cite them by path, and `test_parameter_contract` treats the dated ones (`2026-..`) as historical records; the phase design reports (F5 to F8) are cited the same way | no move; index added (`docs/_audit/README.md`) |
| `docs/phases/` | one record per phase plus `core/` and `F5/` for the reports of that phase | already as the command asks |
| `config/` | every file has a reader (`audit.yaml`, `countries.yaml`, `country_names.yaml`, `deferred_checks.yaml`, `experiments.yaml`, `parameters.json`, `published_potential.yaml`, `settings.yaml`, `technologies.yaml`, `turbines/`) | none |
| tests | 133 test files; the test that loads a moved script was updated (`test_adopt_aligned_cache_keys.py`) | none |
| untracked files | none besides the files of this command | |
| new | `scripts/check_manifests.py` (validity of the manifests: existence and content hash of every registered artifact) | added |

## 3. `GeoFREA_data`

| Folder | Size | Finding | Action |
|---|---|---|---|
| `raw/` | 105 GB, 2,201 files | the inputs; read-only for the pipeline | untouched |
| `outputs/` | 4.6 GB (PRT 99 MB, IND 1.2 GB, BRA 3.3 GB, comparison 0.6 MB) | live results; `outputs/comparison/figures` is written by `potential_maps` (`question_figures.py`) | untouched |
| `outputs/<ISO>/unattended/` | 29 / 14 / 11 files | manifests before each round (the baseline of the deferred check is `20261029_135838`) | kept |
| `interim/IND`, `PRT`, `BRA`, `_mainland_cache`, `cf_tables`, `coverage_audit_59`, `_clip_source_sha256.json`, `_code_digest_cache.json`, `_layer_registry_sha256.json` | 2.0 GB | live caches (readers in `core/geo_utils.py`, `core/code_fingerprint.py`, `technical_potential/cf_table.py`) | kept |
| `interim/IND_aside_75` (756 MB), `PRT_aside_75` (117 MB), `IND_partial_75` (5 KB) | caches set aside before the work of COMMAND 75 (older code), partial cache of an interrupted run | no reader; not a duplicate of the live caches (the lists of files differ), so not deleted | **quarantine** (873 MB) |
| `archive/` | 88 MB (figures of earlier rounds, legacy logs, hash memos) | an archive by design (COMMANDS 68 and 72) | kept |
| `fixtures/synthetic_zzz` | 0.7 MB | synthetic-country fixtures | kept |
| `logs/<ISO>/` | 1 MB each | run logs; the input of `parse_logs.py` | kept |
| `unattended_round_*.log/json` (16 files in the root of the data directory) | stray | `run_unattended.ps1` wrote them to the root | moved to `logs/unattended_rounds/`; the script writes there now |

Caches whose key matches no current code: not enumerated one by one. A clip cache carries its own key (`*.key`) that includes `cache_code`, so a stale one is a miss and is rebuilt; the only caches known to be of an older code are the three set aside above. A proof for the rest needs a run, which this command does not allow.

## 4. Target structure (applied where marked new)

```
D:\Douglas\DOUTORADO\
  database\                      untouched (shared raw)
  GeoFREA\                       repository
    docs\  METHODOLOGY, PROGRESS, CONVENTIONS, LIMITATIONS, OPEN_QUESTIONS, PROJECT_SUMMARY, PIPELINE_GUIDE (new)
      phases\<phase>.md, core\, F5\        phase records and the reports of that phase
      figures\  data\  thesis\  _archive\
      _audit\  README (new), dated and numbered reports, proofs_75_77\ (new), profile_76_tables\
    scripts\  acquire_*, run_unattended.ps1, adopt_*, affected_tests, check_manifests (new), proofs\ (new), profiling\
    src\  tests\  config\
  GeoFREA_data\
    raw\  interim\  outputs\  archive\
    logs\  <ISO>\  unattended_rounds\ (new)
  geoworld_framework\  shared-data-sources\  other\  (kept)
  _quarantine_20261030\  INDEX.md  moves.json  restore_quarantine.ps1
```

## 5. Space

| | Size |
|---|---|
| Deleted (regenerable caches) | 18.6 MB |
| In quarantine | 1,105 MB (1.1 GB) |
| Moved inside the tree | 9 scripts, 12 proofs, 16 round logs (structure only) |

## 6. Checks after the moves

* Quick tests of the affected scripts (adoption, affected tests, unattended check, stamp, deferred check): 37 passed, after the moves.
* **Full suite after all moves: 2013 passed** (30 min, nothing else running).
* `scripts/check_manifests.py` (existence and content hash of the 95 artifacts of each manifest), before and after the moves, identical: **PRT valid, BRA valid, IND 94 of 95**. The one exception, `outputs/IND/climate_forcing/artifacts/forcing.parquet`, was already broken before this command: it is a 25.5 MB half-written file (the run of 2026-10-29 22:01 was killed while rewriting it; the manifest registers 69.9 MB) and cannot be read. Nothing in the cleanup touched it; rebuilding it needs a country run (`--rerun climate_forcing`, about 97 s), which this command forbids. The completion criterion "manifests of the three countries valid" is therefore **met for PRT and BRA and not met for IND**, for that reason alone.
* No reference to a moved path remains (`git grep` of the old script and proof paths outside `docs/_archive`: none). Nothing needed restoring from the quarantine.
