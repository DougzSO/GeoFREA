# Engineering findings of audit 71 closed (COMMAND 73)

Written for Douglas. Manifest schema 2.7, the F5 fingerprint split, the F1b cause and skip, the display layers as COG, the test and CI changes, and the round of the three countries that adopted 2.7. METHODOLOGY 15.2.6; records D-core-048, D-F5-036, D-F5-037, D-F1b-018.

## Result against the completion criterion

| Criterion | Result |
|---|---|
| Manifests 2.7 in PRT, IND, BRA with F2b and F3 registered | yes: 12 `siting/<layer>` and 23 `eligibility/<file>` in each; 91 artifacts per country (78 before) |
| `peak_rss_mb` in every phase | yes: 12 of 12 phases in each country (three passes, below) |
| Content of F1 to F5 unchanged | yes for the data the pipeline uses (aligned rasters, F2b layers, F3 tables, F4 forcing, F5 potential tables); three artifacts changed, each explained below |
| Fingerprint separation test passes | yes: `tests/unit/test_code_fingerprint_f5_split.py` (4 tests) |
| Suite green | 1,864 passed, 0 failed, 28 min 05 s on `main` |
| Push | done |

## What was done

1. **Manifest 2.7 (R71-07, R71-08).** `core/peak_memory.py` (psutil): the peak of a phase is the Windows `peak_wset` of the process when the phase raised it, otherwise the highest working set that a thread sampled every 0.25 s during the phase. It is exact when the phase sets a new process peak and a lower bound otherwise; child processes are not counted. It is in the phase line (`peak RSS 2565 MB`), in the end-of-run table and in `PhaseManifestEntry.peak_rss_mb`. F2b registers `siting/<layer>` and F3 `eligibility/<stem>`, and the consumers of F2b and F3 require those keys. This closes a gap bigger than the one the audit named: the summary artifacts `siting_layers` and `land_eligibility` hold only paths, so before 2.7 an edited layer or table left F3 and F5 current.
2. **F5 fingerprint (R71-06).** The closure of F5 went from 55 to 40 modules (no `viz`, no figure module). Tests: a figure edit leaves F5 unchanged and changes `potential_maps`; an edit of `capacity.py` changes F5; every module of `technical_potential` is numeric or figure and none is both (a new module fails the test until it is classified).
3. **F1 literals (R71-02, rest): not changed, on purpose.** The only strings in the F1 closure that mention the file are "see DECISIONS.md 2026-09-08" and "see DECISIONS.md same date" (`data_acquisition/phase.py:387,438`). They do not contain `docs/DECISIONS.md`, and they are the `source` field of two layers of `layer_registry.json`, an F1 artifact that F1b, F2a and everything after it require. Editing them changes the content hash of F1 and marks the whole BRA chain stale (the 11.7 h of F2a on a cold cache), against item 9 (content of F1 to F5 unchanged). Left for a change that has to rerun F1 anyway.
4. **Display layers as COG (R71-25).** `write_display_layers` uses `safe_raster_write`; a test reads `LAYOUT=COG` and the values back.
5. **R71-22: cause and skip.** See the next section.
6. **`figures: summary`** in `config/settings.yaml` (development rounds); `all` for the thesis build. The synthetic tests pass `"all"` explicitly, so their coverage is unchanged.
7. **Tests (R71-09, R71-27, R71-28, D.2 row 10).** `test_no_legacy_opex_names` iterates `git ls-files --cached --others --exclude-standard` and skips files over 5 MB, `.gz` and `.nc`: it no longer reads ignored archives (the MemoryError of COMMAND 70). `slow` marker on both synthetic modules. New workflow `.github/workflows/unit.yml`: `ruff check` and `pytest tests/unit -m "not slow"` on Python 3.11 and 3.12. New tests: `core/run_logging.py` (8), `core/peak_memory.py` (5), manifest 2.7 in the orchestrator (2) and in the ZZZ world (1), the F5 split (4), the raster audit cache (1), COG display layers (1).
   - **Not done: the session fixture for the ZZZ world.** Each world is already built once per module (`scope="module"`: ZZZ 190 s, ZZZ at 0.1 degree 198 s, ZZZ2 about 200 s) and no two modules share a world. A session fixture would keep the `main.*` monkeypatches alive while the other test modules run, and the hand-validation job of CI depends on the directory names of the module fixtures (`zzz_data0`, `zzz2_data0`). The saving is in the `slow` marker: the unit job skips about 10 minutes of world setup.
   - **CI not verified.** The workflow has not run on GitHub; the suite was run on Windows with Python 3.11 only.

## R71-22: the cause of 63 s against 3,325 s

The land-cover audit of the 111 BRA tiles was a **cold cache**, not contention and not a changed calculation. On 2026-10-14 every tile was a cache hit (0.15 s per tile in the log `fc515236...`). On 2026-10-21 every tile was computed (30 s per tile, log `1ab203b9...`), and all 111 files of `land_cover_tile_cache` carry the date 2026-10-21. The key of that cache holds the country polygon and, since 2026-10-20 (`5be8f65`, D-core-043), the code fingerprint of `raster_inspection.py`; one of them changed between the two runs (the contiguous mask of 2026-10-19, or the code key; the log does not say which).

I reproduced it in this command by accident. The first version of the raster cache sat in `raster_inspection.py`, which was the root of the tile cache, and the first BRA round recomputed the tiles at 31 s each (47 of 111 done in 1,461 s when I stopped it). The per-tile code and its cache are now in `data_quality_audit/land_cover_tiles.py`, the only root of that cache. The cache of the statistics of the other rasters (`raster_audit`, new) is rooted in `raster_inspection.py` and costs minutes, not an hour, when that file changes. F1b of BRA in the final round took 3,881 s because the tiles were cold once more after the move.

Skip of an unchanged input: `inspect_raster_cached` stores the statistics of each raster layer keyed by the SHA-256 of the file (memoised by size and mtime), the country polygon and the code, and an unchanged layer is not read. The vector layers already had the clip cache and the tiles their own.

## Content of F1 to F5

Content hash (`content_sha256`) of every artifact of F1 to F5 in the 2.6 manifest (copied before the round) against the 2.7 manifest, and the canonical hash of the 35 files of F2b and F3 (not registered in 2.6) computed before the round against the registered one.

| | PRT | IND | BRA |
|---|---|---|---|
| Artifacts of F1 to F5 in the 2.6 manifest | 48 | 48 | 48 |
| Identical content | 45 | 47 | 47 |
| Different | `audit_report`, `potential_aggregates_solar`, `potential_aggregates_wind` | `audit_report` | `layer_registry` |
| Files of F2b and F3 equal to the hash before the round | 35 of 35 | 35 of 35 | 35 of 35 |

The differences, each with its cause:

- **`audit_report` (PRT, IND).** The numbers of the layers are the same. What changed are fields measured only when the clip of a vector layer is computed: `geometry_repair` (`n_total`, `n_invalid`, `n_repaired`, `invalid_reasons`) and `geometry_types` of lakes, protected areas, rivers and roads. On a cache hit `vector_inspection._read_clipped_with_cache` returns an empty repair report (`n_total` 0) and the types are read from the GeoPackage (`MultiPolygon` only), while a cold run reports 417 lakes, 1 invalid, and `Polygon` plus `MultiPolygon`. The 2.6 report came from a cold clip, the 2.7 report from a warm one. Not touched here: the clip file is shared with F2a, whose aligned layers are keyed by the content of that file, so rewriting it would invalidate F2a. Finding R73-01.
- **`layer_registry` (BRA).** `source_sha256` of the land cover layer was `None` with the reason "hashing 111 file(s) exceeded the 60 s per-layer budget after 95 file(s)" (D-core-016) in the 2.6 run, and now holds the hashes: the hashing finished within the budget because the files were in the operating system cache. The content of an F1 artifact depends on the speed of the disk. It made F2a run again in BRA (39 s with all its caches current, results identical: the other 47 artifacts are identical). Finding R73-02.
- **`potential_aggregates_solar` and `_wind` (PRT).** The potential tables of the six scenarios are identical; the aggregates differ from the file the 2.6 manifest recorded. That file came from a run on a dirty working tree (`dirty: true`, 2026-10-27 11:12 UTC) and cannot be recovered. The current aggregates are reproducible (a forced rerun gives the same hash) and agree with the potential tables to 1e-13 (energy), exactly (capacity, cell counts). The IND and BRA aggregates are identical to the 2.6 ones. The PRT aggregates of 2.6 are the unexplained ones, not the current.

## Phases redone, time and memory per phase and country

Phases executed (all others resumed): in the three countries data_acquisition, data_quality_audit, siting_layers, land_eligibility, climate_forcing, climate_maps, hazard_context, overview, technical_potential and potential_maps. grid_alignment and external_inputs were resumed in the first pass (BRA ran grid_alignment because of the `layer_registry` above) and rerun with `--rerun` in a third pass so that every phase has a peak. Round times (wall): PRT 2 min 43 s + 25 s; IND 8 min 17 s + 35 s; BRA 87 min 42 s + 12 min 52 s. The first round (PRT 8 min 45 s; IND 33 min + 5 min; BRA stopped after 24 minutes of the tile audit) used the code before the move of the tile module and was repeated.

Wall seconds / peak resident memory (MB) of the last execution of each phase (final manifests). The figures of `grid_alignment` and `external_inputs` are of a run with all caches current (BRA 39 s against 42,176 s cold, in the logs of 2026-10-21); the cold peak of F1 to F4 was never recorded.

| Phase | PRT s / MB | IND s / MB | BRA s / MB |
|---|---|---|---|
| data_acquisition | 52 / 323 | 535 / 907 | 437 / 831 |
| data_quality_audit | 142 / 1,010 | 468 / 3,002 | 3,881 / 4,027 |
| external_inputs | 1 / 251 | 0 / 252 | 0 / 253 |
| grid_alignment | 12 / 288 | 62 / 408 | 39 / 221 |
| siting_layers | 3 / 537 | 26 / 316 | 56 / 432 |
| land_eligibility | 20 / 619 | 249 / 2,565 | 623 / 3,693 |
| climate_forcing | 97 / 352 | 135 / 1,815 | 183 / 2,798 |
| climate_maps | 89 / 696 | 262 / 1,590 | 186 / 2,322 |
| hazard_context | 33 / 893 | 101 / 2,051 | 215 / 3,182 |
| overview | 33 / 733 | 75 / 1,912 | 61 / 3,332 |
| technical_potential | 14 / 327 | 234 / 1,230 | 622 / 2,269 |
| potential_maps | 9 / 685 | 41 / 1,096 | 73 / 1,613 |

Reading: the highest peaks are F1b with 4.0 GB (BRA), land_eligibility 3.7 GB and overview 3.3 GB (BRA), hazard_context 3.2 GB (BRA); the machine has 5.9 GB. The chain F1 to F5 of BRA peaks above the 2.8 GB that D-F7b-007 gave as the highest of the chain, in F1b. The peaks of F6 to F8 are still the sizing figures (D-F5-022 and following).

## New findings

| ID | Sev. | Finding | Evidence | Proposal |
|---|---|---|---|---|
| R73-01 | P2 | The vector part of `audit_report` depends on the state of the clip cache: repair counts and geometry types are measured only when the clip is computed, so a warm cache reports `n_total` 0 and `MultiPolygon` only; the report changes between a cold and a warm run, and with it the staleness of every consumer of `audit_report` | PRT lakes: 417 features and 1 invalid before, 0 after (`phases.data_quality_audit.output.vectors` of the two manifests) | store the repair report and the types beside the clip (`<layer>_clipped.stats.json`) when the clip is made; report "not measured" when the sidecar is absent; do not rewrite existing clips (F2a keys on their content) |
| R73-02 | P1 | The content of `layer_registry.json` depends on the speed of the disk: `source_sha256` is skipped when the hashing of a layer exceeds 60 s (D-core-016), so the same inputs give two contents and the chain after F1 is marked stale | BRA land cover: `None` and a reason in the 2.6 run, 111 hashes in 2.7; F2a ran again | hash through the size-and-mtime memo (`FileHashMemo`, already used by the caches) with no time budget, or keep the hash out of the artifact and in the manifest |
| R73-03 | P2 | `wall_s` of a phase that ran with all its caches current replaces the cold figure in the manifest (BRA `grid_alignment` 39 s; the 42,176 s of the cold run live only in the logs) | final BRA manifest | keep the largest `wall_s` as `cold_wall_s`, or tell a cold run from a cache run in the entry |

## Deviations from the order, in one place

1. The literals of F1 were not changed (item 3 above).
2. The session fixture of the ZZZ world was not made (item 7 above).
3. Between the first and the second round the tile code moved to its own module, which the order did not ask for; the reason is R71-22 itself.
4. The commits of the branch were each checked by the unit and regression suites and the synthetic world of the manifest change; the full suite ran on the branch before the merge and again on `main` after the last change, not on each commit alone.
