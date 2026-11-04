# F3 (`land_eligibility`) memory on BRA: measurement and proposal (COMMAND 90, item b)

Status: **measurement done; the fix (options A and B together) was applied in COMMAND 91 and is in the section at the end.** Cap: 1,536 MB.

## Measurement

`scratchpad/f3_profile.py` runs `build_eligibility` for BRA alone on the machine, with the output and the share caches in a scratch directory (cold caches, as in a round), and samples the resident memory every 0.25 s with the innermost wrapped function as label.

- Wall 1,215 s; baseline of the process 255 MB; **peak 3,631 MB** (the round measured 3,337 MB for the phase).
- Peak by step (MB): `aggregate_to_cells` 3,631 (wind, second scenario), `_check_invariants` 3,332, `_pixel_raster` 3,328, `eligible_fraction` 3,159, `_write_rasters` 2,766, `river_fractions` 2,666 (cache build), `prepare_shared_layers` 1,668 (standing result).
- Solar, the first technology, peaks at 2,655. Wind, the second, climbs 2,780 -> 3,385 -> 3,631 -> 3,524 over its three scenarios.

## Who is responsible

Not one function: the process **holds** about 2.3 GB between calls (the `(top)` level is 2,923 at the wind scenarios) and the steps add 0.3 to 1.3 GB on top of it. The held arrays, in MB for the 3,905 x 3,925 grid (15.3 M pixels; sizes are dtype x pixels, an estimate, not a per-object measurement):

| Held | MB |
|---|---|
| land-cover counts, 11 bands uint16 | 337 |
| population float64 | 123 |
| `pixel_area` float64 (every row repeated across the width) | 123 |
| E2, E1 shares (float32) | 61 + 61 |
| E3 shares per (setback, discharge) of the scenarios, E4 shares per slope maximum (float32, 3 to 5 each) | about 250 + 250 |
| masks: country, slope, land cover, 3 flags | about 75 |
| wind resources, 12 arrays float32, plus 12 validity masks | 735 + 184 |
| elevation float32 | 61 |
| central scenario kept for the whole technology: `eligible` (61) and `excl`, six float32 arrays (367) | 428 |
| each other scenario, transient: `eligible` + `excl` + the work arrays of `eligible_fraction` | about 430 + 120 |

Causes in the code, most to least costly:

1. **The whole grid as float32 pixel arrays for every exclusion**, per scenario, and for the central one throughout the technology. `excl` of the central scenario is stored in `central` and **never read again** (`_write_rasters` takes only `eligible` and `cells`): 367 MB held for nothing.
2. **The inputs are read whole**: the 12 wind rasters and their 12 masks (919 MB) and the shared layers (about 1.5 GB), although every operation is pixel-wise and `aggregate_to_cells` already works in stripes of whole cell rows.
3. `pixel_area` materialised as a 2-D float64 array (123 MB) where one value per row is enough; `required_valid` stores `isfinite` of arrays that are themselves in memory (184 MB).
4. Cache build (`river_fractions`, 2,666): 12 float32 arrays of the thresholds at once; it happens only in a cold round.

## Proposal (not applied)

A. **Free what is dead (small, bit-identical):** drop `excl` right after `aggregate_to_cells` (all scenarios, central included); build `pixel_area` as a row vector broadcast `[:, None]`; compute `required_valid` from `resources` when `valid_pixels` is called. Expected saving 0.5 to 0.7 GB: peak about 3.0 GB. **Not enough alone.**

B. **Stripe the whole pixel engine (what gets the phase under 1,536 MB):** read every input by a window of whole cell rows (`rasterio` windows on the aligned COGs; the share caches as `.npy` memory maps instead of `.npz`), and run `exclusion_fractions` -> `eligible` -> `aggregate_to_cells` on that window; write `eligible_fraction_*.tif` window by window. Resident data then become stripe-sized (a stripe of 4 M pixels is 16 MB per float32 array) plus the cell tables (286 k rows x about 40 columns, 100 MB per scenario, six at a time for the stability table). Expected peak 0.7 to 1.0 GB. `F7b` calls `prepare_shared_layers` too and would read the same windows or keep the old function (it has about 1.5 GB held on BRA by itself; see below).

**Equivalence proof, both options:** every operation is a function of one pixel (E1 to E6, validity, `eligible`) or a sum over the pixels of one cell, and `aggregate_to_cells` already sums in stripes of whole cell rows with the same result as the whole grid. So the cells tables and rasters must be **bit-identical** to the present ones. Test: (1) V-01 frozen fixture and the ZZZ/ZZZ2 unit tests, unchanged; (2) a new test that compares the stripe engine against the whole-grid engine on a synthetic grid for several stripe heights; (3) a BRA run compared artifact by artifact with `core/equivalence.py` (tolerance 0) against the tables of `outputs/BRA/land_eligibility` (kept in `backup_before_89`/current) and the F5 results unchanged.

## Other phases (estimate by size, **not measured**)

- **F5 `technical_potential`** (`pixel_inputs.read_cell_pixels`): reads the fraction raster and every resource whole (61 MB each as float32, one padded copy at a time) and gathers `n_cells x 25` pixels (the cell is 5 x 5 pixels): for BRA wind 181 k x 25 = 4.5 M pixels, 36 MB per float64 array, 9 resources about 330 MB plus the weights. Expected peak under 1 GB. Marked an estimate. **Measured on 2026-11-04: `technical_potential` of BRA peaked at 3,074 MB and that of IND at 1,864 MB; the estimate was wrong** (`docs/_audit/memory_budget_88.md`).
- **F7b `external_validation`** calls `prepare_shared_layers`: the held shared layers (above, about 1.5 GB for BRA) plus the F3 tables. Likely over the cap on BRA; it needs the same windowed reads as B, or a measurement.
- **F4 `climate_forcing`, F6, F8**: no size estimate was made here. They work on cell tables (286 k cells) and members, not pixel grids as far as read; a ZZZ2 scaled run or a measurement with the profile harness is needed before a real round.

## Result of COMMAND 91 (2026-11-04): options A and B applied

`land_eligibility/windows.py` (row-window inputs, stripe engine), `pipeline.build_eligibility` (stripes; `stripe_pixels` or `GEOFREA_F3_STRIPE_PIXELS`, default 1,000,000 pixels), `cells.aggregate_to_cells(stripe_pixels=...)`, share caches as `.npy` folders, riparian grid built one discharge at a time, clipped vectors read only when their shares are built, and `fractions.river_setback_fractions` taking the distance transform in blocks of 8,000 sub-pixel columns with a margin of the largest setback. Decision D-F3-024 (`docs/phases/F3_land_eligibility.md`).

Peak resident memory of F3 on BRA, alone on the machine (`scratchpad/f3_profile2.py`, same sampler as above), outputs in a scratch directory:

| Run | Peak (MB) | Wall (s) | Where |
|---|---|---|---|
| Before (whole grid, 4 M pixel stripes in the cell sums), caches rebuilt | 3,631 | 1,215 | `aggregate_to_cells` |
| Stripes, share caches current (an `.npz` converted) | **1,260** | 606 | `aggregate_to_cells` |
| Stripes, caches rebuilt, 12 riparian arrays together | 2,222 | 1,239 | `river_fractions` |
| + one discharge at a time | 1,817 | 1,194 | `river_fractions` |
| + clipped vectors read only when needed | 1,800 | (the machine slept) | `river_fractions` |
| + distance transform in column blocks (**final**), caches rebuilt | **1,218** | 1,103 | `river_fractions` |

Both final peaks are under the cap of 1,536 MB. The peak of a cold round is the rebuild of the riparian shares (1,218 MB); with the caches current it is the cell sums (1,260 MB).

Equivalence, tolerance 0, artifact by artifact against the output of the round of 2026-11-03 (`scratchpad/cmp_f3_new.py`: parquet tables with `assert_frame_equal(check_exact=True)`, rasters pixel by pixel with grid, nodata and dtype): **27 of 27 identical** in the run with the caches converted and in the run with the caches rebuilt by the new code. The sums by cell are float64 over the same pixels of a stripe, so the order of the additions did not change and no tolerance was needed.

Tests: `tests/unit/test_land_eligibility_stripes.py` (stripe engine against the whole-grid functions that F7b still uses, bit for bit, four stripe heights of which two do not divide the raster; window readers; slope shares by window; `.npy` store and `.npz` conversion; no raster left after a failure) and `tests/unit/test_land_eligibility_fractions.py` (blocks of columns against the whole strip at 0 and 45 degrees). Both were checked to fail when the engine or the block margin is damaged.

### The summary of `land_eligibility` of BRA against the manifest of 2026-10-29

The gate marks `land_eligibility` (the summary JSON) as different from the reference. What the file holds: parameter sets, counts of cells and candidates, areas, shares excluded by constraint, the invalid-pixel share and counts of candidates (k < 1, elevation); **it has no `dist_road_km` statistic.** Every number of it that can be recomputed from tables (cells, candidates, cell area, eligible area, the six excluded shares, k < 1 counts) is identical whether it is taken from the tables of 2026-10-28 (`backup_before_89/BRA_elig`) or from the current ones (equality of the sums to the last bit). The reference file was not kept: its size was 14,687 bytes and now it is 14,689, and the two bytes could not be located. The table columns that did change (`dist_road_km`, `dist_road_capped_share`, and the resource means in the last bit) do not enter the summary. So the claim that the only difference of the summary is the `dist_road_km` statistics is **not** supported; what is supported is that no number of the summary derivable from the tables changed.
