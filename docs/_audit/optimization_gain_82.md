# Optimization gain 82: before and after COMMANDS 75 and 77, from the logs and the manifests

COMMAND 82. No country was run and no benchmark was made for this file: every time comes from `GeoFREA_data/logs/<ISO>/*.log` (parsed with `scripts/profiling/parse_logs.py`,
522 successful phase executions since 2026-10-14) and from the three manifests (schema 2.8). Times are **awake times**: wall time less the sleeps of Windows read from the
System event log (`docs/_audit/profile_76_tables/power_events.json`); CPU is the CPU time the orchestrator logs for the phase. The work is described in
`performance_75.md` (what changed, with the proofs) and `optimizations_77.md` (item by item); this file only measures.

## 1. Periods and how a row is built

| Period | From | To | What the code is |
|---|---|---|---|
| **A, before** | 2026-10-14 | 2026-10-28 15:00 | the code of the first audits (the runs of 14/10 to 27/10) |
| **B, after 75** | 2026-10-28 15:00 | 2026-10-29 11:27 | COMMAND 75 (wind CF table, one GLO-30 pass, F1b/F3/F4 memory) |
| **C, after 77** | 2026-10-29 11:27 | now | COMMAND 77 and the correction of COMMAND 79 (clip fast path for simple lines, shared clip, mainland cache, fingerprint store, open GLO-30 tiles, quiet figures) |

* **Warm round**: the caches are current. Before: the median of the executions of period A that the log marks warm or `always` (a phase with no cache). After: the median of period C
  (period B where C has no execution). **Cold round**: the slowest execution of period A of the phases that have a cache (audit, F2a, F3, F5), the median of the others (the convention of
  the manifest 2.8 `cold_*` fields: the slowest execution under the current code); after: the round of 2026-10-29 for IND and BRA (cold audit, cold F3, F5 by table, F2a adopted), the `cold_*` fields of the manifest for PRT.
* The temperature of a phase comes from its own log lines. A phase with no cache of its own is `always`: its median mixes runs of the same phase in the modes of the day (for the figures
  phases, `figures: summary` and `all`). Where that makes the median meaningless the table says so and the like-for-like pair is the one of `performance_75.md` section 2 (same manifest, same mode).
* CPU can exceed awake time (several threads) and, in period A, awake time can exceed CPU when a step waited for the disk or the network.

## 2. Totals per round (sum of the 12 phases, seconds)

| Country | Round | Before awake | Before CPU | After awake | After CPU | Gain (awake) | Note |
|---|---|---|---|---|---|---|---|
| PRT | warm | 475 | 409 | 252 | 219 | 1.9x | both measured |
| PRT | cold | 1,586 | 1,143 | 435 | 354 | 3.6x | both measured (F2a cold 501 s to 139 s) |
| IND | cold, with F2a rebuilt before / adopted after | 21,004 | 29,052 | 3,811 | 5,143 | 5.5x | F2a is 9,678 s of the before; **after, F2a was adopted** (6 s), not rebuilt |
| IND | cold, F2a left out | 11,326 | | 3,805 | | 3.0x | like for like (no F2a in either) |
| BRA | cold, with F2a rebuilt before / adopted after | 41,473 | 46,822 | 2,753 | 2,441 | 15x | F2a is 18,774 s of the before |
| BRA | cold, F2a left out | 22,699 | | 2,746 | | 8.3x | like for like |
| IND | warm | 2,111 | 1,846 | not measured | | | no warm round was run after 77 (section 5) |
| BRA | warm | 3,237 | 2,608 | not measured | | | same; the cold round after (2,753 s) is already below the warm round before |

Reading: the large factors of the cold rounds have two parts. The adoption of the aligned layers (D-core-044) removes F2a entirely (a decision about caches, not an optimization of the code: when the layers are
equal it costs nothing, when they are not it is rebuilt). The rest, 3.0x in IND and 8.3x in BRA, is the work of 75 and 77: the F5 wind table (BRA 10,721 s to 230 s), the shared clip and the line shortcut
(audit: BRA 6,563 s to 636 s; IND 4,334 s to 2,452 s) and and the cold F3 shares (after the memory and stripe work of 75, the shared clip of 77), from 4,134 s to 1,117 s (BRA) and 3,437 s to 470 s (IND).

## 3. Phase by phase and country

"Before" columns: executions of period A that are not cold (n, median awake, median CPU) and the slowest execution of period A (the cold cost where the phase has a cache). "After": period C (B where C has none).
A ratio above 1 is not a regression when it compares a warm median with a cold after-round (marked in section 4) or two figure modes (climate_maps).

### PRT

| Phase | Before: n | awake med (s) | CPU med (s) | slowest awake (s) | slowest CPU (s) | After (C): n | awake (s) | CPU (s) | peak RSS after (MB) | after/before awake (med vs med) |
|---|---|---|---|---|---|---|---|---|---|---|
| data_acquisition | 11 | 50 | 20 | 168 | 125 | 6 | 15 | 15 | 320 | 0.31 |
| data_quality_audit | 10 | 87 | 80 | 404 | 258 | 4 | 50 | 27 | 785 | 0.58 |
| grid_alignment | 7 | 12 | 10 | 648 | 385 | 6 | 6 | 5 | 2,302 | 0.53 |
| siting_layers | 8 | 3 | 1 | 6 | 1 | 3 | 2 | 1 | 558 | 0.66 |
| land_eligibility | 15 | 20 | 17 | 129 | 34 | 3 | 17 | 15 | 660 | 0.87 |
| external_inputs | 3 | 1 | 0 | 1 | 0 | 4 | 0 | 0 | 323 | 0.19 |
| climate_forcing | 13 | 102 | 90 | 226 | 103 | 4 | 70 | 71 | 391 | 0.68 |
| hazard_context | 10 | 30 | 28 | 35 | 32 | 3 | 28 | 26 | 1,032 | 0.94 |
| climate_maps | 10 | 24 | 23 | 291 | 286 | 3 | 34 | 33 | 690 | 1.46 |
| overview | 12 | 66 | 63 | 90 | 81 | 3 | 14 | 14 | 815 | 0.22 |
| technical_potential | 20 | 14 | 13 | 210 | 188 | 3 | 4 | 4 | 634 | 0.30 |
| potential_maps | 22 | 66 | 64 | 462 | 457 | 3 | 9 | 8 | 709 | 0.13 |


### IND

| Phase | Before: n | awake med (s) | CPU med (s) | slowest awake (s) | slowest CPU (s) | After (C): n | awake (s) | CPU (s) | peak RSS after (MB) | after/before awake (med vs med) |
|---|---|---|---|---|---|---|---|---|---|---|
| data_acquisition | 8 | 538 | 426 | 2,382 | 1,028 | 4 | 765 | 715 | 1,006 | 1.42 |
| data_quality_audit | 7 | 468 | 433 | 4,334 | 7,748 | 2 | 2,365 | 3,806 | 1,560 | 5.05 |
| grid_alignment | 4 | 67 | 60 | 9,922 | 12,413 | 5 | 7 | 4 | 430 | 0.10 |
| siting_layers | 5 | 26 | 13 | 29 | 15 | 1 | 24 | 14 | 1,367 | 0.96 |
| land_eligibility | 12 | 232 | 202 | 3,437 | 5,897 | 1 | 470 | 452 | 2,316 | 2.02 |
| external_inputs | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 317 | 0.75 |
| climate_forcing | 11 | 135 | 112 | 153 | 126 | 1 | 97 | 82 | 478 | 0.72 |
| hazard_context | 7 | 98 | 83 | 144 | 102 | 1 | 86 | 78 | 2,223 | 0.88 |
| climate_maps | 8 | 43 | 41 | 678 | 669 | 1 | 116 | 114 | 1,580 | 2.69 |
| overview | 9 | 133 | 122 | 273 | 205 | 1 | 28 | 25 | 1,362 | 0.21 |
| technical_potential | 15 | 233 | 221 | 2,445 | 2,384 | 1 | 64 | 60 | 1,316 | 0.27 |
| potential_maps | 18 | 137 | 134 | 2,634 | 2,448 | 1 | 19 | 19 | 1,342 | 0.14 |


### BRA

| Phase | Before: n | awake med (s) | CPU med (s) | slowest awake (s) | slowest CPU (s) | After (C): n | awake (s) | CPU (s) | peak RSS after (MB) | after/before awake (med vs med) |
|---|---|---|---|---|---|---|---|---|---|---|
| data_acquisition | 8 | 442 | 327 | 647 | 476 | 3 | 284 | 274 | 850 | 0.64 |
| data_quality_audit | 7 | 618 | 404 | 6,563 | 7,857 | 1 | 636 | 481 | 1,813 | 1.03 |
| grid_alignment | 5 | 38 | 30 | 18,840 | 22,081 | 4 | 19 | 17 | 448 | 0.51 |
| siting_layers | 6 | 57 | 30 | 62 | 32 | 1 | 58 | 29 | 1,013 | 1.02 |
| land_eligibility | 12 | 628 | 534 | 4,134 | 5,953 | 1 | 1,117 | 1,081 | 3,397 | 1.78 |
| external_inputs | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 382 | 0.75 |
| climate_forcing | 11 | 175 | 146 | 205 | 164 | 1 | 112 | 94 | 790 | 0.64 |
| hazard_context | 8 | 192 | 149 | 231 | 170 | 1 | 157 | 137 | 2,737 | 0.82 |
| climate_maps | 8 | 60 | 58 | 614 | 496 | 1 | 80 | 78 | 2,212 | 1.34 |
| overview | 9 | 208 | 186 | 247 | 212 | 1 | 32 | 28 | 1,609 | 0.15 |
| technical_potential | 12 | 673 | 635 | 10,721 | 10,442 | 1 | 230 | 196 | 2,369 | 0.34 |
| potential_maps | 15 | 146 | 110 | 1,258 | 1,235 | 1 | 41 | 39 | 1,753 | 0.28 |

## 4. The comparisons that are like for like, and the reading of the ratios above 1

| Phase | Country | Before | After | Same temperature and mode? | Reading |
|---|---|---|---|---|---|
| technical_potential (F5) | BRA | 10,721 s awake (10,442 CPU), exact integral, cold | 230 s (196 CPU), table integral | yes (cold, both) | 47x. The only change of a number on purpose (METHODOLOGY 15.3.1, error 6.5e-9 against 1e-5) |
| technical_potential (F5) | IND | 2,445 s slowest (cold); 233 median | 64 s (cold 250 s in the manifest) | yes | the table cuts the cold CF; the warm run was already cheap |
| technical_potential (F5) | PRT | 210 s slowest, 14 median | 4 s warm, 13.7 s cold | yes | 70.6 s to 0.36 s for the CF alone |
| data_quality_audit (F1b) | BRA | 6,563 s slowest (cold clips; land cover 3,469 s) | 636 s (cold, whole round) | yes (cold) | 10x |
| data_quality_audit (F1b) | IND | 4,334 s slowest (cold; protected 2,208 s, roads 1,249 s) | 2,452 s (cold) | yes (cold) | 1.8x; the closed boundary lines of `protected` go back to the exact intersection after COMMAND 79 (not re-measured) |
| data_quality_audit (F1b) | PRT | 404 s slowest, 87 median | 73 s (cold), 50 median | yes | roads clip 117 s to 9 s |
| grid_alignment (F2a) | BRA / IND | 18,774 / 9,678 s cold | 7 / 6 s (adopted) | **no: adoption is not a rebuild** | a rebuild after 77 is not measured for IND and BRA |
| grid_alignment (F2a) | PRT | 501 s cold (median of 2) | 276 s after 75, 140 s after 77 (cold) | yes | 3.6x on the only country measured cold after 77 |
| land_eligibility (F3) | BRA | 4,134 s slowest (cold shares); 628 median (warm) | 1,117 s (cold shares) | cold to cold: 3.7x; the warm median is not comparable | peak memory 4,860 MB to 3,397 MB (target 3,000 MB not met) |
| land_eligibility (F3) | IND | 3,437 s slowest (cold); 232 median | 470 s (cold) | cold to cold: 7.3x | peak 2,893 MB to 2,316 MB |
| overview | PRT / IND / BRA | 66 / 133 / 208 s median | 14 / 28 / 32 s | yes (same tables, no redraw) | 4.5x to 6.5x: `quiet_figure` and the grouped tables |
| climate_maps | IND / BRA | 248 / 169 s CPU (manifest before, `all` figures) | 114 / 78 s CPU | yes (manifest pair) | 2.2x. The medians of the table above (43 / 60 s) are runs in `figures: summary` mode, so the ratio of 2.7 / 1.3 there compares unlike modes |
| climate_maps | PRT | 83.6 s CPU (cProfile, profile 76) | 31.8 s CPU | yes | 2.6x |
| potential_maps | PRT / IND / BRA | 66 / 137 / 146 s median | 9 / 19 / 41 s | yes | 3x to 7x; the maps read the F5 outputs and, in PRT, the exact-integral mode was in the profile of the phase (profile 76 B.3); the share of the fingerprint store and the quiet figures was not separated |
| hazard_context, climate_forcing | all | 30 to 192 s, 102 to 175 s | 28 to 157 s, 70 to 112 s | yes | 6% to 36%: band-wise indicators and single reads; the memory, not the time, was the aim |
| data_acquisition | PRT / BRA | 50 / 442 s median | 15 / 284 s | partly: the network and the `--rerun` of the day move it | not an effect of the work; IND rose (538 to 765 s) with the forced re-fetch of the GWA masks |
| siting_layers, external_inputs | all | 0 to 57 s | 0 to 58 s | yes | no change expected, none seen |

Peak memory (working set of the process, `core/peak_memory.py`): BRA `land_eligibility` 4,860 MB (period A maximum) to 3,397 MB; BRA `hazard_context` 3,182 to 2,737 MB; BRA `climate_forcing` 3,389 to 790 MB;
IND `land_eligibility` 2,893 to 2,316 MB; IND `grid_alignment` cold 3,889 MB (period B) against 430 MB adopted. The F5 and the maps stay under 2.4 GB.

## 5. What was not measured after, and why

* **Warm round of IND and BRA after 77.** Only one round was made per country (2026-10-29, `outputs/<ISO>/unattended/`), and it was cold for the audit and F3. The pipeline compares IND and BRA with the reference manifest the first time it
  executes each phase on the merged code (D-core-050); that execution is the next warm measurement, and it is a country run, which this command forbids.
* **Cold F2a of IND and BRA on the merged code.** The aligned layers were adopted (proof on PRT). The BRA saving of the one-pass GLO-30 read (about 4,300 s of 18,707 s) is an expectation from the PRT window (168 s to 87 s), not a measure. PRT cold F2a:
  501 s, 276 s (75), 140 s (77).
* **The audit and the clips after COMMAND 79** (the restriction to simple LineStrings sends 8,707 closed lines of IND `protected` back to the exact intersection). Seconds expected; not re-timed. Its isolated effect is in `optimizations_77.md`.
* **Per-step CPU**: the logs hold CPU per phase only; steps have wall time. Per-step CPU exists only in the micro-benchmarks of `profile_76.md` part B.
* **Figures in mode `all` after 77 for IND and BRA**: the round used the configured mode; the PNG equivalence of item h is proved on PRT (95 of 95).
* **The sleeps** of the round of 2026-10-29 are nil (the computer was kept awake), so awake time equals wall time there; the before rows are corrected with the event log.
* **Not an optimization**: `data_acquisition` and the climate downloads depend on the network and the day; read their rows as noise.
