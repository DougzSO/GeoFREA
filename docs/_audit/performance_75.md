# Performance 75: what the pipeline costs now, and the proof that its results did not change

COMMANDS 75 to 80. Branches `perf/75-performance` and `perf/77`, merged into `main` with COMMAND 80. Profile that led to the work: `docs/_audit/profile_76.md`.
Per-item detail of the second half (COMMAND 77, with the correction of COMMAND 79): `docs/_audit/optimizations_77.md`.

**Rule of the work.** Measure before and after; prove that the results are equal by canonical content hash (`core/content_hash.py`, the hash of the manifest);
one change per commit, with tests; a change that cannot be proved equal is not applied. The one result that moves on purpose is the wind capacity factor
of F5 (METHODOLOGY 15.3.1), within a measured tolerance.

**Times are awake times.** The wall time of a long run includes the sleeps of Windows (`profile_76.md` A.1: the "BRA land cover 26,534 s" is 3,063 s awake; the
"IND rivers 25,599 s" is 610 s awake). Every time below is `wall - slept`, with the sleeps read from the System event log (Kernel-Power 42 to the next
Power-Troubleshooter 1); where two numbers are given, the second is CPU. CPU can exceed awake time (several threads).

## 1. Result

| Target of COMMAND 75 | Result |
|---|---|
| F5 (`technical_potential`) of BRA under 15 min of CPU | **Met.** 10,442 s CPU (2.9 h, exact integral) before; 230 s awake, 196 s CPU now (table integral). |
| Peak memory of every phase under 3 GB | **Not met.** BRA `land_eligibility` peaks at **3,397 MB** (cold shares, see 3). Every other phase of PRT, IND and BRA is under 3 GB in the measured round (largest: BRA `hazard_context` 2,737 MB, BRA `technical_potential` 2,369 MB, IND `land_eligibility` 2,316 MB). |
| Items 2 to 4 of the command identical by hash | **PRT: proved, 94 of 94 artifacts** of the eleven phases from `data_quality_audit` to `potential_maps` (`cumulative_equivalence_77_PRT.json`), 95 of 95 PNG by pixels. **IND and BRA: pending**, verified by the deferred check (D-core-050) the first time the pipeline executes each phase; see 4. |

## 2. Before and after, by country and phase

"Before" is the last execution recorded in the reference manifest of each country (`outputs/<ISO>/unattended/20261029_135838/manifest_before.json`, the
state of the pipeline at the start of the unattended round; CPU seconds). "After" is the unattended round of 2026-10-29 (awake seconds, CPU seconds, peak resident memory of
the process). Two caveats govern how to read it.

1. **The round was measured before COMMAND 79** restricted the covered-line shortcut of the clip to simple LineStrings. The restriction sends 8,707 closed lines of IND `protected`
   and the multipart lines back to the exact intersection: seconds, not minutes (rivers and roads, which have no such lines in the sample, are unchanged). The cost
   difference is negligible; the times below were not measured again.
2. Several "before" values are **warm** executions (the caches were current) and the "after" values are **cold** ones (the clip changed, so the clip caches, the
   shares of F3 and the clips of the audit were built again). Where that is so the row says it; a cold run slower than a warm one is not a regression.

**IND**

| Phase | Before (CPU s) | After awake (s) | After CPU (s) | Peak after (MB) | Note |
|---|---|---|---|---|---|
| data_acquisition | 380 | 411 | 391 | 1,006 | forced by `--rerun`; no change expected |
| data_quality_audit | 8,194 (wall 3,511) | 2,278 | 3,728 | 1,560 | cold: all clips rebuilt; protected 2,208 s, roads 1,249 s and rivers 495 s were the earlier cold steps (`profile_76.md` A.4) |
| grid_alignment (F2a) | 9,967 CPU, 6,878 awake (cold) | 6 | 4 | 372 | the aligned layers were adopted under D-core-044, not rebuilt; cold F2a was 3,889 MB |
| siting_layers | 14 | 24 | 14 | 1,367 | |
| land_eligibility (F3) | 5,502 (wall 3,057) | 470 | 452 | 2,316 | cold shares (the 5,502 s CPU of the reference is the cold round that preceded it, wall 3,057 s) |
| external_inputs / climate_forcing | 0 / 99 | 0 / 97 | 0 / 82 | 317 / 478 | |
| hazard_context | 83 | 86 | 78 | 2,223 | |
| climate_maps | 248 | 116 | 114 | 1,580 | `quiet_figure` (item h) |
| overview | 60 | 28 | 25 | 1,362 | `quiet_figure` |
| technical_potential | 216 | 64 | 60 | 1,316 | |
| potential_maps | 24 | 19 | 19 | 1,342 | |

**BRA**

| Phase | Before (CPU s) | After awake (s) | After CPU (s) | Peak after (MB) | Note |
|---|---|---|---|---|---|
| data_acquisition | 310 | 282 | 274 | 830 | |
| data_quality_audit | 332 (warm clips) | 636 | 481 | 1,813 | cold: all clips rebuilt in 636 s; the earlier cold steps alone were roads 1,028 s, rivers 1,275 s, land cover 3,469 s (`profile_76.md` A.4) |
| grid_alignment (F2a) | 30 (warm) | 6 | 5 | 448 | adopted; the last cold F2a was 18,707 s awake |
| siting_layers | 29 | 58 | 29 | 1,013 | |
| land_eligibility (F3) | 543 (warm shares) | 1,117 | 1,081 | **3,397** | cold shares; **peak above the 3 GB target** |
| climate_forcing | 117 | 112 | 94 | 790 | |
| hazard_context | 145 | 157 | 137 | 2,737 | |
| climate_maps | 169 | 80 | 78 | 2,212 | `quiet_figure` |
| overview | 85 | 32 | 28 | 1,609 | |
| **technical_potential (F5)** | **10,442** (exact integral) | **230** | **196** | 2,369 | wind CF table (D-F5-039) |
| potential_maps | 76 | 41 | 39 | 1,753 | |

The awake times of the twelve phases add up to 3,599 s (1.0 h) for IND and 2,751 s (0.8 h) for BRA in that round, with the aligned layers adopted and every clip, share and figure rebuilt.
For comparison, `profile_76.md` A.3 counts 4 cold executions of IND (7.4 awake hours) and 2 of BRA (10.4 awake hours) since 2026-10-14, dominated by F2a and the clip caches.

## 3. What the work changed, with its proof

| Where | Change | Proof (content) | Gain measured |
|---|---|---|---|
| F5 | wind CF integral by cubic spline on the exact integral, option `technical_potential.wind_cf_integral: table\|exact` (D-F5-039, METHODOLOGY 15.3.1) | maximum absolute CF error **3.2e-9** (PRT), **6.5e-9** (1 million BRA pixels), against the tolerance 1e-5; `tests/unit/test_cf_table.py` | CF of PRT 70.6 s to 0.36 s; of BRA 1,040 s to 6.9 s; F5 of BRA 10,442 s CPU to 196 s |
| F2a | elevation, slope and slope bins from one pass over the GLO-30 tiles | byte-identical; `aligned_equivalence_PRT.json`, 28 of 28 artifacts | PRT 168 s to 87 s (the BRA saving, about 4,300 s, was not measured) |
| F1b | raster statistics in row blocks, only the valid values kept; the chunk of a wide raster is cut by pixels | same numbers | peak memory of IND 3.0 GB to 1.6 GB |
| F1b | repair counts and geometry types stored beside the clip cache | cold and warm runs report the same | (consistency, R73-01) |
| F1 | the hash of a layer has no time budget and is kept by path, size and mtime | | (R73-02) |
| F3 | cells summed in stripes of rows; riparian shares and slope bins reduced to the scenario combinations; only the central scenario keeps its pixel arrays | exactly the sums of the whole grid | peak memory of F3, see section 2 |
| F4 | hazard indicators by bands of rows (a fifth of the memory); the four daily crops read once; the QC summaries read the member ids once each | same fields and summaries | |
| overview | tables grouped by member without a copy | same tables | |
| core | manifest 2.8: `cold_wall_s`, `cold_cpu_s`, `cold_peak_rss_mb`, `cold_started_at`, `cold_code_fingerprint` beside the last execution (R73-03) | | |
| core | `scripts/adopt_aligned_cache_keys.py`: adopt the aligned layers made under an earlier code, only after an automatic equivalence proof on both revisions (D-core-044) | `cumulative_equivalence_77_PRT.json` | avoids the cold F2a: 18,707 s awake (42,176 s wall) in BRA and 6,878 s awake (31,913 s wall) in IND, `profile_76.md` A.1 |
| tests | `scripts/affected_tests.py` (selection by changed files), xdist and testmon as development dependencies | the full suite remains the gate of a merge | |
| COMMAND 77 | items 1a (clip fast path, restricted by COMMAND 79), 2 (clip shared by the audit, F2a and F3), 4 (mainland and union cache), 7 (fingerprint store), 8 (GLO-30 tiles kept open), h (figures without redraw), j (2 GB check), k (`keep_awake`) | see `optimizations_77.md` | see `optimizations_77.md` |

## 4. Equivalence of IND and BRA: what is proved and what is deferred

* **Proved** (content hash, by artifact): PRT, eleven phases, 94 of 94; the clips of **IND** `protected`, `roads`, `rivers` and `lakes`, whole layers, equal to the clips made before COMMAND 77
  (`equals_exact`, tolerance 0; `clip_layers_equivalence_IND.json`); the GLO-30 rasters, the mainland geometry and the union of PRT, IND and BRA (`glo30_equivalence_item8.json`, `mainland_equivalence_item4.json`).
* **The unattended round of 2026-10-29 found a defect and the work corrected it.** IND `land_eligibility` and the phases after it differed (42 of 95 artifacts), because item 1a kept
  8,705 closed non-simple boundary lines of the protected areas as they were while the exact intersection rewrites them (GEOS nodes the ring and drops vertices; Hausdorff distance 0, 148 of
  2.25 million pixels of the coverage differ by up to 0.02). COMMAND 79 restricted the shortcut to simple LineStrings (`clip_shortcut_diagnosis_IND.json`). BRA differed only in the F5
  artifacts that depend on the wind table, with the change of configuration that explains them (7 artifacts), and in `audit_report` (see below).
* **Deferred.** No new round was made after the correction. The pipeline compares, the first time it executes each phase of IND and BRA on the merged code, the content hash of every artifact with the reference
  manifest above (`config/deferred_checks.yaml`, `core/deferred_check.py`, D-core-050), writes `outputs/<ISO>/deferred_check.json`, and stops before the next phase on a difference that no change of configuration
  explains. The expected differences are the F5 artifacts of BRA that depend on the wind table (the configuration fingerprint of the phase changed) and the `audit_report` of BRA, flagged for review: its difference in the
  round was the count of `geometry_types` and the reference copy of the file was not kept, so what differs cannot be read back; nothing computes from the report.
* **Before the first IND or BRA run on the merged code**, adopt the aligned layers (the cache code of the aligned layers is now `c147200ba18b`):
  `python scripts/adopt_aligned_cache_keys.py <ISO> --revision perf/75-performance --proof docs/_audit/cumulative_equivalence_77_PRT.json`
  (the script puts back the keys of the revision first, so it can be run again). Without it F2a is rebuilt from the start (6,878 s awake in IND and 18,707 s in BRA in the last cold executions).

## 5. Limits of what was measured

* The tables are one round per country, not a distribution. A cold phase of a rebuilt cache is slower than the warm one before it; a comparison is valid only between like temperatures, and the notes say which is which.
* Awake times use the sleeps of the Windows event log; the round ran with the computer kept awake, so the correction is nil in it.
* The whole-country IND and BRA numbers of the items of COMMAND 77 are included in the round; they were not isolated one by one (the isolated gains are on windows, `optimizations_77.md`).
* The peak memory of a phase is the working-set peak of the process (a lower bound, `core/peak_memory.py`); child processes are not counted. The target of 3 GB was missed by BRA `land_eligibility`
  (3,397 MB), whose cold shares build the pixel arrays of the largest grid; reducing it further is not part of this work.
