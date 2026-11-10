# Map of the memory peak of F5 (`technical_potential`) and `potential_maps` (COMMAND 119, item 3)

Written for: the author, to decide where the memory of F5 and its maps goes before anything is changed. Read-only: no code was changed and no phase was run for this document. No code is proposed here.

**What is measured and what is estimated.** The peaks are the manifest values of the round 1d34ab23 (2026-11-09, `peak_rss_mb` of the process while the phase ran, `core/peak_memory.py`): BRA `technical_potential` 3,410 MB and `potential_maps` 2,548 MB; IND 1,794 and 1,737; PRT 395 and 722. The sizes of the arrays below are **arithmetic on row counts and dtypes** read from the parquet metadata and the grid metadata, not per-operation measurements: nobody has measured F5 operation by operation (the audit `docs/_audit/memory_budget_88.md` measured phases, `scripts/size_f5_to_f8.py` measured phases at the size of BRA with test values). Where an estimate and a measurement cannot be reconciled it is said.

## Sizes by country (from the files of the round)

| | BRA | IND | PRT |
|---|---|---|---|
| grid (rows x columns) | 3,905 x 3,925 = 15.3 M pixels (float32 58 MB, float64 117 MB) | 2,750 x 2,930 = 8.1 M (31 / 61 MB) | 525 x 340 = 0.18 M (under 1 MB) |
| 0.05 degree lattice | 781 x 785 = 613 k cells | 550 x 586 = 322 k | 105 x 68 = 7 k |
| cells table (F3) | 286,043 rows | 112,948 | 3,939 |
| `forcing.parquet` of F4 | 10.58 M rows (37 members), 153 MB on disk | 4.18 M rows, 67 MB | 0.15 M rows, 2 MB |
| candidates central, solar / wind | 190,521 / 178,289 | 93,701 / 75,535 | 3,415 / 3,332 |
| candidates, largest scenario (permissive) | 200,075 solar, 200,035 wind | 107,919 / 99,793 | 3,640 / 3,638 |
| rows of `potential_<tech>__<scenario>.parquet` | solar 7.0 to 7.4 M (37 members); wind 4.9 to 6.2 M (31 members) | solar 2.7 to 4.0 M; wind 1.2 to 3.1 M | 75 k to 135 k |

Columns of `forcing.parquet`: `cell_id` int64, `member` (dictionary, int8 index), `delta_rsds`, `dT`, `delta_wind` float32, `dT_isolated_native_cell` bool: 22 bytes per row. The potential table has `cell_id` int64, `member` categorical (int8), `P_MW`, `CF`, `E_MWh` float64: about 33 bytes per row. The wind model reads nine resource layers (Weibull A and k and air density at 100, 150 and 200 m), the solar model reads PVOUT and the temperature factor.

## F5, `technical_potential` (`pipeline.py: build_technology_potential`), in order of size on BRA

| # | operation | what it allocates (BRA) | IND | PRT | kind |
|---|---|---|---|---|---|
| 1 | `read_cell_pixels` (wind only): reads the F3 pixel fraction and the nine resource rasters **whole**, gathers the 5 x 5 pixels of each candidate cell, keeps the eligible ones (`pixel_inputs.py`) | whole rasters: float32 58 MB each, masked read and `astype` and `filled` make 3 to 4 copies in flight (about 200 MB), `weight` and `padded` float64 117 MB each; `gather` gives (178 k to 200 k cells x 25) float64 = 36 to 40 MB per layer, nine of them held in `values` (about 340 MB) while `w[usable]` and `v[usable]` are built (up to 4.5 M pixels x 10 arrays x 8 B = 360 MB): **about 1.0 GB at the top of the operation**, once per scenario | about 0.5 GB | negligible | **partitionable by row window of cells** (a cell takes its 25 pixels from its own rows; this is what `windows.py` does for F3), but today it reads the whole grid |
| 2 | `forcing` read and `by_member` (`groupby("member")` then `set_index("cell_id")` per member) | `forcing` 10.58 M rows x 22 B = 233 MB in Arrow, about 300 MB in pandas with `member` turned to strings; `by_member` is a second copy of every row (+230 to 300 MB). Both stay alive for the whole technology, over the three scenarios: **about 0.6 GB held** | about 0.25 GB | under 10 MB | **partitionable by member** (members are independent: one `taken = factors.iloc[...]` per member) and **by cell** (a cell reads its own rows); today whole |
| 3 | per-member loop: `prepared.member(...)` capacity factor | the wind model works in blocks of `PIXELS_PER_BLOCK` = 1 M pixels (about 100 MB of temporaries, `cf_models.py`): already in blocks. Solar is linear in the cell means: (cells,) arrays | small | small | **already blocked** (wind); per cell (solar) |
| 4 | `pieces` then `pd.concat(pieces)` and `write_table` (zstd) | 37 frames of 190 k rows, 7.0 M rows x 33 B = 233 MB, then the concatenation another 233 MB (both alive at the concat), then the Arrow conversion for the writer (about 200 MB more), per scenario; `table` stays referenced until the next scenario replaces it: **0.5 to 0.7 GB** | 0.25 to 0.35 GB | small | **partitionable by member or by cell block** (each piece is one member); `write_table` takes a whole frame today |
| 5 | `candidates` frames of the three scenarios, `frame.sort_values("cell_id")`, `validate_candidates` | 190 k x about 25 columns x 8 B = 38 MB per scenario, 3 scenarios held: about 115 MB (200 k rows at most each) | about 55 MB | small | `validate_candidates` is a reduction (min and max against ranges): global but streamable; the sort is on `cell_id` |
| 6 | `energy_by_member` (37 arrays of `len(frame)`), `aggregate_scenario` | 37 x 190 k x 8 B = 56 MB per scenario | 28 MB | small | the sums are global reductions, streamable by member |
| 7 | `weibull_distribution_report(candidates[central])` | P1, P50 and P99 of a few columns of 178 k values | trivial | trivial | **global** (a percentile of the whole country), small |

Arithmetic sum at the top, wind on BRA: about 0.3 GB (the process before any data) + 0.6 (forcing and `by_member`) + 0.1 (candidates) + 1.0 (operation 1) = **about 2.0 GB**; at the concatenation of operation 4: 0.3 + 0.6 + 0.1 + 0.15 (prepared pixels) + 0.5 = about 1.7 GB. The measured peak is **3,410 MB** and the phase runs solar and wind in one process. **A gap of about 1.4 GB between this arithmetic and the measure is not explained here**: it can be what the earlier technology leaves resident in the heap (Python does not give all of it back), temporaries of pandas and Arrow that the arithmetic does not count, or the process in which the phase ran (OQ-068 and `docs/_audit/f3_peak_118.md`: the manifest does not record which phases ran before in the same process). Only a per-step measurement closes it.

## `potential_maps` (`maps.py: build_potential_maps`, `absolute_maps.py`, `state_figures.py`, `question_figures.py`, `display_layers.py`), on BRA

| # | operation | what it allocates (BRA) | IND | PRT | kind |
|---|---|---|---|---|---|
| 1 | `pd.read_parquet(potential_<tech>__central)` whole, then the m0 rows (`maps.py`); `absolute_maps._national_totals` reads the potential tables again, scenario by scenario | 7.0 M rows (solar) x 33 B = 233 MB, 5.5 M (wind) = 180 MB, about twice that while pandas converts from Arrow; the three scenarios are read one after another and are not all alive together, but the heap does not return all of it | 0.1 to 0.2 GB | small | **partitionable**: only the m0 rows and the sums per scenario are used; whole today |
| 2 | maps of the question figures (`question_figures.py`, 811 lines) and of the states (`state_figures.py`): polygons of the admin1 units and of the neighbours (`ctx`, `load_neighbours`), matplotlib figures (the log shows "more than 20 figures opened" in the unit tests) | geometry of 27 admin1 units, the neighbours cut to the territory, canvases and `np.zeros(grid.shape + (4,))` float64 on the lattice: 613 k x 4 x 8 B = 20 MB per classed map; figures at the dpi of the style guide: tens to a few hundred MB while alive | similar, smaller | small | **global in form** (a figure needs the whole territory) but small per figure; the peak depends on how many figures stay alive |
| 3 | `class_breaks` (quantile and Fisher-Jenks of the values above zero) and the colour limits by `CLIP_PERCENTILES` | `np.unique` and `np.quantile` on 190 k to 613 k values: a few MB | few MB | few MB | **global**, by definition (the class limits are percentiles of the country), small |
| 4 | the display layers at 0.01 degree (`display_layers.py: ensure_display_layers`) | **not built for BRA or IND** (no `display_*.tif` in their artifacts: the rule `country_needs_fine_layer` found a cell of at most four pixels on the map). Only PRT has them (8 files). Were they built for BRA: nine resource arrays + the fraction + the pixel area + the `kron` upsampling, each float64 117 MB: more than 2 GB | (would be 1.2 GB) | tiny, built | **global on the grid** (whole-grid arrays and a `block_sum` check), and **not run** where the countries are large |

Measured: BRA `potential_maps` 2,548 MB, IND 1,737, PRT 722 MB (PRT is the largest in relation to its size because it is the only country that builds the display layers and all its figures). The arithmetic of the table gives well under that for BRA; the difference is again not explained here, and the figure phases of `potential_maps` are the one where the process also holds matplotlib and the geopandas layers.

## Is there a path by stripes today, and why it is not used

- **F3 has one** since COMMAND 91: `land_eligibility/windows.py` (`StripeInputs`, `ScenarioStripes`, row windows of the grid, `aggregate_to_cells` by stripes of whole cell rows) and the tests that show the result is the same for any stripe height (`tests/unit/test_land_eligibility_stripes.py`).
- **F5 has a blocked path only for the capacity-factor arithmetic of the wind model** (`PIXELS_PER_BLOCK` = 1,000,000 pixels at a time). Everything around it (the pixel inputs of operation 1, the forcing of operation 2, the concatenation of operation 4) is whole.
- **Why it is not used:** it was not written. `OQ-068` records that the phases after F3 are over the cap in BRA and IND, that "the same remedy applies (per-step measurement, windows, equivalence at tolerance 0)", that the priority set by the author on 2026-11-04 is `technical_potential` and `hazard_context` first, and that "nothing of it is implemented yet". COMMAND 91 did F3 only. `read_cell_pixels` is a module of its own that could take the row windows of `windows.py`, but no command asked for it.

## What this map leaves open (for the author, not proposed)

1. A per-step measurement of F5 on BRA (the same kind COMMAND 91 made for F3), to attribute the 3,410 MB; without it the largest candidates above (operations 1, 2 and 4) are arithmetic.
2. Whether the aim is to put BRA `technical_potential` under 1,536 MB or only to know the cost; the cap of a phase process is not enforced by the guard (it waits for memory before layer processes, `core/memory_guard.py`).
3. The cap itself: IND, which was under it on 2026-11-04 (1,372 and 1,415 MB), is over again on 2026-11-09 (1,794 and 1,737), with the same F5 code: the same open question as F3 (what is resident in the process around the phase).
