# F5 memory reduction, items a, b and d (COMMAND 126, step 1; step 6 of COMMAND 124 reduced)

Written for: the author. Branch `f5-memory`. The official outputs, the manifests and `references/latest.json` were not touched; IND and BRA were not run.

## What changed

| item | where | what |
|---|---|---|
| a | `technical_potential/pixel_inputs.py::read_cell_pixels` | The fraction raster and the nine resource rasters are read in bands of cell rows (`BAND_PIXELS` = 1,000,000 pixels, rasterio windows over open datasets), never whole. Every pixel goes through the same operations as before (read with mask, cast to float32, `NaN` fill, weight = fraction x row area, gather of the 5 x 5 pixels of each cell). The cells are processed by band (a stable sort by lattice row) and their pixels are put back in the order of the table. The checks and their messages are the same (cell outside the raster, raster not on the grid, no eligible pixel, weight sum against the F3 area), made after all bands. |
| b | `technical_potential/pipeline.py::build_technology_potential` | At the end of each scenario `pieces`, `prepared`, `energy_by_member`, `qc`, `aggregate`, `p_mw`, `area`, `cell_ids` and the loop temporaries are released, so the next `read_cell_pixels` does not start with them. |
| d | `technical_potential/pipeline.py::_write_potential_in_blocks` | The 31 or 37 pieces are no longer concatenated into one table. They are taken off the list as they are consumed and written through `TableWriter` in blocks of exactly 1,048,576 rows (the row group of pyarrow's `write_table`), the last one shorter, so the file has the same rows in the same order and the same row groups. A scenario without rows still goes through `write_table`. |

**Not changed:** `climate_forcing/forcing.py` (so `assert_forcing_usable`), `forcing["member"].astype(str)` (item c), the per-member loop, `prepare_pixels`. `git diff main --stat` touches `pixel_inputs.py`, `pipeline.py`, the new test and this document.

## Equivalence

1. **Unit tests** (`tests/unit/test_f5_memory_equivalence.py`, 22 tests). The old `read_cell_pixels` is kept in the test as the oracle.
   - Pixels: `tobytes()` equal for the weights and for each resource, and `offsets` equal, with bands of 1, 400, 3,000 and 10^9 pixels, the table in order and shuffled, a grid that starts and ends inside a 0.1 degree cell (padding in the first and last bands), no candidate cell, and the four errors with the same message.
   - Table: the file of `_write_potential_in_blocks` has the same SHA-256 as `pd.concat` + `write_table` for 0, 10, 1,048,575, 1,048,576, 1,048,577, 2 x 1,048,576, four half-groups, ten pieces of 300,000 rows, a piece of three groups and empty pieces; same number of row groups; the pieces list is empty afterwards.
   - Whole of F5 on the synthetic world of the F5 tests (solar and wind, three scenarios): all the artifacts are byte-identical to the ones the old code gives (`read_cell_pixels` and the writing replaced by the old versions in the same test).
2. **PRT in a scratch directory** (`GeoFREA_data/work/f5_126_old`, `f5_126_new`: a copy of `outputs/PRT` and `interim/PRT`, `raw` and `external` as junctions, removed afterwards). Old code = `git archive main`; new code = this branch. `main.py PRT --phases technical_potential --rerun technical_potential` in each, fresh process, same Python 3.11.9 and libraries (pyarrow 25.0.1, pandas 3.0.6).
   **32 of 32 artifacts identical by SHA-256** between old and new (17 Parquet, 15 other: COG, display layers and JSON).
3. **Against the official PRT outputs:** the 15 non-Parquet artifacts are identical; **the 17 Parquet files differ in bytes from the official ones, in old and in new alike**, because the official ones were written with `parquet-cpp-arrow 24.0.0` and the environment now writes `25.0.1` (the `pandas` metadata of the schema also changes, and `potential_aggregates` string columns are typed differently). Read back by value (every column, `NaN` equal to `NaN`) the 17 are equal. So the criterion "bit-identical to the current code" holds; "bit-identical to the files already on disk" does not hold for Parquet for a reason that is not this change, and it means that **any F5 rerun in this environment rewrites the official Parquet bytes**.
4. **Synthetic input of the size of BRA, not BRA data** (`scratchpad/synth126.py`, `synth_table126.py`): 3,900 x 3,900 pixels (15.2 M), nine resource rasters, 304,351 candidate cells, 6.24 M eligible pixels; and 37 pieces of 286,000 rows (10.58 M rows). Fresh process each, `GDAL_CACHEMAX` = 256 as in `settings.yaml`.
   The SHA-256 of the pixels (weights and each of the nine resources) is the same old and new, and the SHA-256 of the 288 MB Parquet file (11 row groups) is the same old and new.

## Peak memory, before and after

**PRT, F5 alone** (RSS in MB; manifest `peak_rss_mb` 403 old, 398 new). PRT is too small for the change to show: the phase peak is `prepare_pixels` of the first wind scenario (402 old, 397 new), which this command does not touch, and the new `read_cell_pixels` peaks about 10 MB higher than the old one (333 to 339 against 324 to 327; band lists and the open datasets, at the size of a PRT raster).

| step (wind) | old: start, peak in step | new: start, peak in step |
|---|---:|---:|
| `read_cell_pixels` central | 320, 324 | 311, 333 |
| `prepare_pixels` central | 318, 402 | 314, 397 |
| `read_cell_pixels` restrictive | 317, 321 | 320, 335 |
| `read_cell_pixels` permissive | 323, 327 | 316, 339 |
| write of the potential, permissive | 311, 322 (`write_table`; the concat before it peaks at 313) | 323, 323 (`_write_potential_in_blocks`) |

**Synthetic, size of BRA** (MB; start = RSS before the call):

| call | old: start, peak, after | new: start, peak, after | peak above the start |
|---|---:|---:|---|
| `read_cell_pixels` (6.24 M pixels kept) | 116, 1,201, 604 | 118, 921, 606 | 1,085 -> 803 |
| concat and write of 10.58 M rows (37 pieces) | 475, 847, 846 | 475, 556, 155 | 372 -> 81 |

The result of the read (about 490 MB: ten float64 arrays of the kept pixels) is the same, and the 256 MB of the GDAL cache is in both; what is gone is the whole raster, its weight and the padded copies (about 280 MB less). In the write, the new code holds 81 MB above the pieces and **gives the pieces back (155 MB after, against 846)**: that is item d and the part of b that falls on `pieces`.

## What would be left of the peak in BRA, by arithmetic (not measured)

Base: the measured steps of `docs/_audit/f5_peak_measured.md` (BRA, run b: F5 alone in a new process; sampled peaks).

| point of F5 (wind, BRA) | measured, MB | after a, b and d, MB | how |
|---|---:|---:|---|
| start of `read_cell_pixels` of the 2nd and 3rd scenario | 1,656 and 1,597 | about 1,090 | b: the 0.55 GB the previous scenario left bound is released; 1,084 is the level before the first scenario |
| peak of `read_cell_pixels`, 3rd scenario (permissive) | 2,244 (2,307 recorded for the phase) | **about 1,400** | 2,244 - 550 (b) - 283 (a, the difference measured on the synthetic input) |
| peak of the `pd.concat(pieces)` of the 3rd solar scenario | 1,867 | about 1,250 | 1,867 - 550 (b) - about 115 (d: 195 above the start becomes 81) |
| **`forcing['member'].astype(str)` (item c, not done)** | **2,137 wind, 1,971 solar** | **2,137** | unchanged |

So **the three items take about 0.8 GB off the point that was the peak, and the peak of the phase moves only to the next step, `forcing['member'].astype(str)`, which is 2,137 MB in the same run: the phase peak falls by about 0.1 to 0.2 GB (2,307 -> about 2,140 to 2,200), from where item c would have to bring it down.** In the same arithmetic the official round (3,410 MB, 0.8 GB of it not located in `f5_peak_measured.md`) would fall by at most the same 0.1 to 0.2 GB if the peak of the round is also at one of these two points; where it is in the round is not known. None of this reaches the 1,536 MB figure: the floor of the phase after a, b and d is the process (about 0.25 GB), `forcing` and `by_member` (about 0.6 GB), the candidates and the pixel arrays of the scenario (about 0.5 GB) and the GDAL cache.

The arithmetic assumes that the synthetic difference of the read (283 MB) holds in BRA, that the 0.55 GB measured as retained is released entirely (the sizes of the objects add up to more than that), and that the allocator returns the memory (the "after" of the synthetic write shows that it does).

## Fingerprints (the blast radius)

Closure fingerprints, 19 phases and 13 caches, Python 3.11, against `main`: **5 phases change** (`technical_potential`, `potential_maps`, `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`: they read F5 code) and 14 do not; **the 13 caches do not change**. The next round rewrites those five phases for every country (the orchestrator sees `code_changed`), and the Parquet bytes of F5 with them (see point 3).

## What was not done

- IND and BRA were not run; the BRA figures above are arithmetic over the measured tables and a synthetic input, not a measurement of the real BRA phase.
- Item c (`forcing["member"]` without the full-memory `astype(str)`) and `assert_forcing_usable` were left out by the command. They are what is left of the peak.
- `BAND_PIXELS` was not tuned; the band lowers the transient but also reads each raster in more calls (the synthetic read took 8 to 15 s in both versions, no slower in the new one).
- The full unit suite of this branch: see the commit message and the report of the command.
