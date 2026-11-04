# Memory budget of F2a and F2b (COMMANDS 88 and 89)

The cold F2a of BRA was stopped by the memory guard on a 6 GB machine. The cap is 1.5 GiB (1,536 MB) of resident memory per process (`config/memory_budget.json`, `core/memory_budget.py`).
Every layer runs in its own child process (`core/layer_process.py`) and waits for its measured peak plus a margin to be free (`core/memory_guard.py`).

"Before" and the BRA rows other than those marked *measured 2026-11-03* are the table reported by the session of COMMAND 88, **a measurement of the previous session, not kept in a file**.

## Peak resident memory per layer, BRA (MB; cap 1,536)

| Layer | Before | After | Δ against the existing raster | Source of "after" |
|---|---|---|---|---|
| glo30 | ≥ 2,062 | 672 | not compared (the full run is about 3 h) | budget test, worst block |
| solar | 541 | 409 | equivalent (tolerance of CONVENTIONS) | session table |
| wind | 1,182 | 610 | equivalent | session table |
| land_cover | 1,504 | 1,504 (chunk of 1,024 MB kept) | exact by construction; 180 of 15.3 M pixels differ at a 16 MB chunk (below) | session table |
| land_cover_counts | 1,078+ | 1,108+ (tile loop, partial); final stretch 789 | not compared (full run over 30 min) | session table; **final stretch measured 2026-11-03** |
| population | 2,001 | **637** (`sum_to_grid`, 64 MB window) | 923 pixels out of tolerance against the GDAL raster of 400 MB, max 2.9 people; the total differs by +19 (216,464,622 against 216,464,603) | **measured 2026-11-03** |
| grid, poi, roads, lakes | 785 / 780 / 1,000 / 385 | 773 / 776 / 881 / 375 | identical (Δ = 0) | session table |
| rivers | 1,554 | 1,065 | identical (Δ = 0) | session table |
| physical (F2b) | 361 | 295 | n/a | session table |

All the layers measured or tested are at or under 1,536 MB. Two figures are not a complete measure and are said so: `land_cover_counts` (the tile loop was stopped by the time limit at 1,108 MB; its strips have a constant size, and the stretch after it, the one that holds the 322 MB array, peaks at 789 MB) and `glo30` (a budget test on the worst block, not the 3 h run).

## Decisions

### 1. Land cover, 180 pixels (`scratchpad/lc180_cmp.py`, 2026-11-03)

`mosaic_land_cover` with a 16 MB chunk against `BRA_land_cover_aligned.tif` (1,024 MB chunk): 180 pixels differ, all inside the country (151 rows, 57 columns; classes 30↔10 in 111 of them).
- Chunk edges: no concentration in a row or a column (at most 9 per column, 4 per row).
- Tile edges (3°): 0 in x, 3 in y of 180 within one pixel of an edge.
- Centre of the target pixel on an edge of the source pixels: 180 of 180 in x and in y; a sample of all the pixels gives 100 % in x. The WorldCover pixel is 3/36,000 deg, so 120 of them make a 0.01 deg pixel and every centre is a tie of the nearest neighbour.

Conclusion: nearest-neighbour ties broken by the warp chunk, not a defect. Nearest takes one source pixel, so the chunk cannot make a value wrong; it picks one of two equally near. The 1,024 MB chunk stays (D-F2a-027).

### 2. Population (`pop_run.py`, `val.py`, 2026-11-03)

Cause: the source is EPSG:4326, 0.00083333333000 deg (not exactly 1/1200), origin -73.989583022, so a target pixel is 12.00000005 source pixels and every target edge falls 0.4996 to 0.4998 of a source pixel into one. GDAL's `Resampling.sum` resolves that edge by the origin of its chunk: the 3,606 pixels that differ between a 400 MB and a 64 MB window are all in columns 243, 244, 979 and 980 (not in the seams of the strips: 61 of 3,606 are within a row of a seam of the 400 MB partition, 354 of the 64 MB one, which is the share of the rows the seams cover).

Against the exact area-weighted sum of the source (on the 3,606 pixels): the 400 MB window has 359 pixels off by more than 1e-3 (max 2.9), the 64 MB window 877 (max 3.9), `sum_to_grid` none (max 8.4e-7).

`sum_to_grid` on the whole BRA:

| Window | Time | Peak RSS |
|---|---|---|
| `sum_to_grid` 16 MB | 70 s | 551 MB |
| `sum_to_grid` 64 MB (default) | 84 s | 637 MB |
| `sum_to_grid` 200 MB | 75 s | 1,285 MB |
| GDAL `Resampling.sum`, 64 MB | 970 s | 1,067 MB |

The three exact rasters are identical bit by bit; the nodata mask equals that of the existing raster (0 pixels differ); the total is 216,464,622.15 against 216,464,577.42 (GDAL 64 MB) and 216,464,603.14 (existing): the exact sum is the one that is right, and the others are off by 45 and 19 people in 2.16e8 (2e-7).

Rule of the command (peak ≤ 1,536 MB and time ≤ 1.5 × the present one): met with a wide margin (84 s against 970 s). Adopted (D-F2a-026, METHODOLOGY 16.2.2). The difference to the earlier raster is not an equivalence in the sense of CONVENTIONS (923 pixels out of tolerance, max 2.9 people): it is a correction, recorded as a difference by design of the round (`config/deferred_checks.yaml`, `aligned/population`).

### 3. land_cover_counts, final stretch (`lcc_tail.py`, 2026-11-03)

The mask of the pixels outside the country, the write of 11 bands (uint16, deflate with predictor, 256-pixel tiles) and the tags, on an array of the size of BRA with random counts, alone on the machine: 26 s, peak 789 MB (the process held 497 MB before it, the 322 MB array included), file 192 MB. Under the cap. No method changed. The measurement used `safe_raster_write`, the writer of the function, which ends the file as a COG (A-07), so the copy to the COG of the 11 bands is inside the 789 MB.

## Cold round of 2026-11-03: measured peaks per layer (MB, `interim/<ISO>/*/layers.json`)

No layer of any country waited for the guard (`waited_s` = 0) and every layer is at or under the cap of 1,536 MB. For BRA these figures replace the "session table" ones above (`config/memory_budget.json`).

| Layer | PRT | IND | BRA |
|---|---|---|---|
| elevation (glo30) | 485 | 855 | 984 |
| solar | 163 | 336 | 409 |
| wind (largest of the 12 layers) | 201 | 573 | 610 |
| land_cover | 1,351 | 220 | 1,473 |
| land_cover_counts | 904 | 1,079 | 1,207 |
| population | 470 | 703 | 742 |
| grid / poi | 188 / 240 | 536 / 582 | 772 / 777 |
| roads / lakes | 311 / 141 | 785 / 258 | 887 / 376 |
| rivers | 172 | 568 | 1,064 |
| F2b layers (largest) | 108 | 213 | 297 |

Wall time of BRA F2a: 14,996 s (elevation 11,117 s, land_cover_counts 2,482 s, land_cover 498 s, population 95 s).

**F3 (`land_eligibility`) was over the cap and is not any more**: before COMMAND 91 it peaked at 3,337 MB on BRA (1,119 s), 2,097 MB on IND, 342 MB on PRT; run by stripes of rows (D-F3-024, `docs/_audit/f3_memory_90.md`) it peaks at 1,438 MB on BRA (1,128 s), 834 MB on IND, 337 MB on PRT, with the outputs identical at tolerance 0. It runs inside the main process, not in a layer process.

## Phases after F3, measured in the round of 2026-11-04 (peak resident memory of the phase, MB; cap 1,536)

Run by `scripts/run_unattended.ps1` in an independent PowerShell, one country at a time, with the memory guard on; the peak is the one the orchestrator records for the phase (`peak_rss_mb` of `unattended_round_20261104_*.json`, the whole process, not a layer). These phases have no `layers.json` (they are not layer processes). Over the cap in **bold**; nothing was changed in code.

| Phase | PRT | IND | BRA |
|---|---|---|---|
| climate_forcing | - | - | 713 |
| hazard_context | - | - | **2,913** |
| climate_maps | - | - | **2,394** |
| overview | 839 | 1,414 | **1,773** |
| technical_potential | 688 | **1,864** | **3,074** |
| potential_maps | 852 | **1,542** | **1,781** |

Wall time (s): BRA climate_forcing 111, hazard_context 157, climate_maps 79, overview 31, technical_potential 638, potential_maps 37; IND overview 104, technical_potential 247, potential_maps 20; PRT 19, 14, 9. Smallest free physical memory during the run: PRT 2,492 MB, IND 1,439 MB, BRA 835 MB; no phase was stopped by the guard.

Six phases are over the cap, five of them in BRA; `potential_maps` of IND is 6 MB over. They are reported here and not corrected (the command of 2026-11-04 said so): the next step is the same as for F3 (a per-step measurement, then a fix with an equivalence proof, `docs/_audit/f3_memory_90.md`), starting with `technical_potential` and `hazard_context`; the cause was not measured. The size estimate of `f3_memory_90.md` for F5 (under 1 GB for BRA wind, from the 4.5 M candidate pixels) was wrong: the phase peaked at 3,074 MB.

The F5 potential tables match the cells of the current F3: for each of the 18 combinations of country, technology and scenario, the cells of `potential_<tech>__<scenario>.parquet` are exactly the cells of `candidates_<tech>__<scenario>.parquet` (3,449 to 183,351 cells, none on only one side), and the capacity per eligible km2 is one constant per technology and scenario (relative spread 8e-16), so the areas agree (`scratchpad/f5_vs_f3.py`).

The reference store kept the three rounds automatically at the end of the runs (`references/864efbcb.../<ISO>`, 52, 54 and 52 files) because the deferred check had no phase DIFERENTE: the phases it knew (F1 to F3, `climate_forcing` and `hazard_context` of PRT and IND) were IDENTICO against the state of 2026-11-04, and the six phases rerun here are not in that round (they were `stale_upstream`), so they were SEM_REFERENCIA, with nothing to compare.

## F5 again on the code of COMMANDS 95 and 96 (round of 2026-11-04, afternoon; COMMAND 97)

`technical_potential` and `potential_maps` of IND and BRA, run by `scripts/run_unattended.ps1` in an independent PowerShell, one country at a time, on the code that writes the ensemble table (D-F5-041) and checks the display layers by the tolerance of CONVENTIONS (D-F5-040). Peak resident memory of the phase (MB; cap 1,536):

| Phase | IND | BRA |
|---|---|---|
| technical_potential | **1,372** (was 1,864) | **2,613** (was 3,074) |
| potential_maps | 1,415 (was 1,542) | **1,840** (was 1,781) |

Wall time (s): IND technical_potential 64, potential_maps 23; BRA 226 and 38 (earlier round: 247 and 20; 638 and 37). The lowest available memory of the system during the runs was 1,298 MB (IND) and 934 MB (BRA). The two IND values and the BRA `technical_potential` are lower than in the first round and `potential_maps` of IND is now under the cap; the round of the morning ran with other programs open and the code was not the same, and the cause of the drop was not investigated (no change aimed at memory was made). Over the cap now: BRA `technical_potential` (2,613), BRA `potential_maps` (1,840) and, from the first round, the BRA phases `hazard_context`, `climate_maps` and `overview` that did not run again; IND `technical_potential` 1,372 is under the cap. Nothing was corrected.

## What is left

- Phases after F3 over the cap: the five of BRA (`hazard_context` and `climate_maps` and `overview` from the round of the morning; `technical_potential` 2,613 and `potential_maps` 1,840 from the round of the afternoon); IND is under the cap in the afternoon values; no fix made.
- F6 to F8 have no real-country run and no measured peak; F7b reads the whole-grid layers (OQ-068).

