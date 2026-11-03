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

## What is left

- The cold round of the three countries has not been run (`docs/PIPELINE_GUIDE.md`, "Group 3 round").
- `glo30` and `land_cover_counts` have no complete BRA measurement; the guard measures them in the round (`layers.json` of each country keeps the peak of every layer).
