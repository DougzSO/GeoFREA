# Cleanup of audit 71 (COMMAND 72), log

Written for Douglas. Every action of the cleanup list of `docs/_audit/2026-10_general_audit_71.md`, in the order executed: path, size, destination. Date of the actions: 2026-10-27. Sizes from `os.stat` and `du -sk` taken before the action.

Items not in the order of COMMAND 72 were not executed: 4 (the branches `feat/cache-restamp` and `backup-before-split`), 16 (`data_quality_audit` caches) and the script `place_w5e5_tasmax.py` of item 7 (kept until OQ-051).

## Repository `D:\Douglas\DOUTORADO\GeoFREA` (commits on `chore/audit71-docs`)

| Item | Action | Size | Result |
|---|---|---|---|
| 1 | Deleted `regression-fixtures.tar.gz` (ignored by git, workflow retired on 2026-10-06) | 380,498,564 B (363 MiB) | done |
| 2 | `git worktree remove` of `GeoFREA_wt58c` (20,120 KB), `GeoFREA_wt59` (20,216 KB), `GeoFREA_wt60` (15,692 KB), `GeoFREA_wt61` (22,703 KB), `GeoFREA_wt63` (15,800 KB), each with a clean `git status` first | 94,531 KB | done |
| 3 | `git branch -d` of the 21 merged branches: `docs/coverage-54`, `docs/geometry-dem-55`, `feat/display-layers-wiring`, `feat/display-resolution`, `feat/final-round-62`, `feat/fingerprint-granularity`, `feat/mapfigure`, `feat/mapfigure-geo`, `feat/mapstyle`, `feat/potential-maps-absolute`, `feat/potential-maps-v2`, `fix/coverage-59`, `fix/era5-first-year`, `fix/geometry-dem`, `fix/manifest-config`, `fix/oq060`, `fix/resume-integrity`, `fix/state-classes`, `stage-r/fix-46`, `stage-r/groups1-2`, `stage-r/oq053` | negligible | done (`-d` refuses an unmerged branch; none refused) |
| 5 | Six dead symbols deleted (`land_eligibility/figures.py:_resolution`, `overview/style.py:country_outline`, `major_rivers`, `load_relief`, `technical_potential/absolute_maps.py:CountryUnits`, `core/run_logging.py:PeriodicProgress.track`) and the six imports that became unused | 80 lines | done; commit `72252fd` |
| 6 | The two unread keys of `thresholds:` in `config/experiments.yaml` (`satisficing_lcoe_usd_per_mwh`, `capacity_factor_min`); `regret_quantile`, which `robustness_analysis/decision.py:74` reads, stays | 18 lines | done; the audit named the whole block, `regret_quantile` is read |
| 7 | Deleted 10 one-shot scripts (`archive_geofrea_data.py` 287 lines, `migrate_clip_cache_keys.py` 75, `patch_era5_cells.py` 151, `place_local_inputs.py` 121, `register_isimip3b_from_copy_log.py` 69, `qc_plants_vs_grid.py` 118, `plot_plants_over_grid.py` 88, `extend_era5_gust.py` 279, `era5_status.py` 134, `era5_ext_queue.py` 456) and `tests/unit/test_era5_ext_queue.py` (154 lines, the 8 tests of `era5_ext_queue`). They stay in the git history (last commit that holds them: `72252fd`) | 1,778 lines of scripts + 154 of tests | done |
| 8 | Moved the PNG files of five report folders to `GeoFREA_data/archive/docs_figures_<folder>/`: `2026-10_data_diagnostics_figures` (9 files, 2,077,336 B), `coverage_alignment_54` (12 files, 1,038,150 B), `potential_maps_v2` (8 files, 2,277,638 B), `potential_maps_absolute` (2 files, 724,822 B), `audit_potential_65` (3 PNG, 444,644 B; its three JSON files stay). The image links of the five reports became text naming the file; a note under each title says where the images are. File list: `GeoFREA_data/archive/_docs_figures_move_log_72.json` | 6,562,590 B | done; no markdown image link of the repository points to a missing file (checked) |
| 9 | `.pytest_cache` unreadable (ACL) | none | **not done**: `takeown`, `icacls` and `Remove-Item` answer "access denied" from this session; needs an elevated shell (`takeown /F .pytest_cache /R /D Y`, then `icacls .pytest_cache /grant %USERNAME%:(OI)(CI)F /T`, then remove). The suite ran with `-p no:cacheprovider` |
| R71-29 | `.gitignore`: `data/` became `/data/`; the line `!/docs/data/` is no longer needed and was removed. `docs/data/` is still tracked and no other `data` or `outputs` folder exists outside `.venv` | none | done |
| R71-19 | `is_complete_download` of `fetchers/era5.py` and `fetchers/cmip6.py` (identical; only tests called it) became `core/downloads.py`; the two tests became one (`tests/unit/test_core_downloads.py`) | 30 lines | done |

## Data `D:\Douglas\DOUTORADO\GeoFREA_data` (outside git; the machine log is `GeoFREA_data/archive/_cleanup_72_data_log.json`)

Nothing was written or removed in `D:\Douglas\DOUTORADO\database\raw`. The manifests, the artifacts and the caches of F1 to F5 were not touched.

| Item | Action | Size (B) | Destination |
|---|---|---|---|
| 10 | Deleted `interim/BRA/grid_alignment/BRA_slope_native.tif` | 323,317,267 | none (no reader in `src/`, `tests/`, `scripts/` or `main.py`) |
| 10 | Deleted `interim/IND/grid_alignment/IND_slope_native.tif` | 147,827,050 | none |
| 10 | Deleted `interim/PRT/grid_alignment/PRT_slope_native.tif` | 3,513,466 | none |
| 11 | Deleted `raw/gadm/BRA/superseded_largest_polygon_v1/` | 21,659,500 | none |
| 11 | Deleted `raw/gadm/IND/superseded_largest_polygon_v1/` | 13,223,716 | none |
| 11 | Deleted `raw/gadm/PRT/superseded_largest_polygon_v1/` | 8,218,983 | none |
| 12 | Deleted `raw/era5/IND/IND_fg10_annual_max.before_cell_patch.nc` | 1,024,914 | none |
| 12 | Deleted `raw/era5/IND/IND_fg10_annual_max.before_extension.nc` | 933,663 | none |
| 13 | Deleted `outputs/BRA/manifest.json.before_stamp` | 159,368 | none |
| 13 | Deleted `outputs/IND/manifest.json.before_stamp` | 161,426 | none |
| 13 | Deleted `outputs/PRT/manifest.json.before_stamp` | 146,205 | none |
| 14 | Deleted `outputs/ZZZ/` | 136,045 | none |
| 14 | Deleted `interim/ZZZ/` | 393,415 | none |
| 15 | Moved `raw/elevation/` (bundled DEMs of BRA, IND and PRT, read by no phase) | 345,675,010 | `D:\Douglas\DOUTORADO\database\unused\elevation\` (new folder) |
| 17 | Moved `logs/BRA/legacy_manifests`, `logs/BRA/legacy_runs`, `logs/PRT/legacy_manifests`, `logs/PRT/legacy_runs`, `logs/_snapshots`, `logs/_moves` | 2,182,108 | `GeoFREA_data/archive/logs_legacy_20261027/` (same relative paths) |
| 18 | Pruned the keys of `D:\Douglas\DOUTORADO\database\raw\...` from the hash memos: `interim/_clip_source_sha256.json` (15 of 49 keys), `interim/BRA/grid_alignment/input_sha256.json` (116 of 1,063), `interim/IND/...` (58 of 602), `interim/PRT/...` (10 of 53). No phase reads that folder, so the keys were never looked up | about 0.37 MB of text | the four files as they were: `GeoFREA_data/archive/hash_memos_20261027/` |

Totals: 520,715,018 B deleted (0.52 GB), 345,675,010 B moved out of `GeoFREA_data` (0.35 GB), 2,182,108 B archived inside it. Together with the repository folder (the tarball of 0.38 GB and five worktrees of 0.09 GB) the cleanup frees about 1.34 GB on `D:\Douglas\DOUTORADO\GeoFREA*`; the 1.1 GB the audit listed under the author's verdict (item 16 and the rest of item 4) is untouched.
