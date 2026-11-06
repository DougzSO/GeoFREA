# COMMAND 98 audit: resume after an interruption (inventory, step 0)

Status: inventory only. No code was changed. Written 2026-11-05.

Goal of the command: any interruption (power loss, killed process, memory guard, Ctrl+C) loses at most about 5 minutes of work in any phase, F1 to F8 and the figures, and the relaunch continues from where it stopped with a result identical to the continuous run.

"Identical" is defined by `core/content_hash.py` (A-02), which is what `unattended_check.py` uses: parquet by column names, Arrow types and row values in row order (row-group layout, compression and file metadata ignored); GeoTIFF by data, dtype, shape, CRS, transform and nodata (tags and creation options ignored); JSON by the parsed document. So a parquet or raster assembled from checkpointed pieces is identical to the continuous one when the values and their order are.

## 1. Evidence and its limits

- Durations come from the round `20261029_135838` (`logs/unattended_rounds/unattended_round_20261029_135838.log`, awake seconds) and the BRA manifest. In that round F2a ran with the aligned layers adopted from the earlier revision, so its 5.6 s is a cache hit, not the cost of the work.
- Cold F2a: `scripts/run_unattended.ps1` states about 42,000 s for BRA. For IND, the ledger (`interim/IND/grid_alignment/layers.json`) records 4,157 s of wall time for the elevation layer of the last completed cold run (it also produces `slope` and `slope_counts`, ledger status `cached`); the run interrupted on 2026-11-05 had done 1,450 of 2,750 strips in 2,893 s (`child.log`). Wall time includes any sleep of the computer.
- F6, F7 and F8 have never run on real data. The BRA manifest ends at `potential_maps`. Their durations are not measured; the sizes below come from the code and the configuration, and the column says "not measured".
- "Verified" means the code was read for this audit. "To verify" means the unit is inferred from names and progress logs and is read in step 1 before any change.

## 2. What is resumable today

| Mechanism | Where | What it gives | Gap |
|---|---|---|---|
| Layer cache by key | `core/cache_key.py`, `grid_alignment/alignment.py:320`, F2a/F2b layers | A finished layer is not recomputed when its key is current | The unit is the whole layer, so an interrupted layer restarts from zero |
| One child process per layer | `core/layer_process.py` | Memory returns to the system between layers; ledger `layers.json` is replaced atomically after every layer | The child's `payload.pkl` lives in a temporary directory of the layer; an abrupt stop leaves it. No work inside the layer survives |
| Manifest written after every phase | `core/orchestrator.py:826` (`.tmp` + `replace`) | A killed run leaves the manifest of the last finished phase | No `fsync` (see section 4) |
| ERA5 per-year files | `fetchers/era5.py` (`.part.nc` then rename, `[annual] i/N`) | Yearly checkpoints, atomic | No `fsync`; verification by presence only (to verify) |
| DEM tiles | `fetchers/copernicus_dem30.py:70` (`.part`, size against `Content-Length`, then `replace`) | Tile-level resume; a short file is rejected | Whole tile restarts (no Range); no `fsync`; an existing `.tif` is trusted without a size check |
| WorldCover tiles | `fetchers/esa_worldcover.py:81` (streamed) | To verify whether it uses `.part` | To verify |
| GWA files | `fetchers/wind.py:331` (`.tmp.tif`); the 2026-11-05 log shows `completed from [...]` per product | Product-level reuse | Each product takes about 1 min, below the limit |
| Reference store, deferred check | `core/reference_store.py:76,154`, `core/deferred_check.py:161` | `.tmp` + `os.replace` | No `fsync` |
| `cf_table` | `technical_potential/cf_table.py:102` | `.tmp` + `os.replace` | No `fsync` |

## 3. Inventory by phase and layer

Duration is the BRA awake time of the whole phase in the round of 2026-10-29 unless stated. "Lost today" is what a kill at the worst moment costs.

| Phase | Layer or stage | Natural unit | BRA duration | Lost today | Needs a checkpoint (unit above about 5 min) | Status |
|---|---|---|---|---|---|---|
| F1 data_acquisition | DEM, WorldCover, WDPA, HydroRIVERS, GHSL downloads | File or tile | 282 s warm; cold is hours, network bound | One file in transfer | Only the Range or hash step for large files | Partly resumable (`.part`); verify all fetchers |
| F1 | GWA products, IND stitching | Product (about 1 min) | 844 s for IND | One product | No | Verified: reuses finished products |
| F1 | ERA5 and CMIP6 | Year; file | hours cold | One year or file | No; add `fsync` and hash or size check | Verified for ERA5; CMIP6 to verify |
| F1b data_quality_audit | Land-cover tile audit | Tile (`raster_inspection.py:778`) | 636 s BRA, 2,278 s IND | The phase | Yes for IND (38 min) and BRA (11 min) | To verify (likely per-tile, results are summaries) |
| F2a grid_alignment | Elevation, slope, slope bins (`glo30_aligned_outputs`) | Block of grid rows (`_OUTPUT_BLOCK_ROWS`), final once processed | 5.6 s warm; about 42,000 s cold BRA; 4,157 s wall IND for this layer | The whole layer | Yes | Verified: blocks are independent |
| F2a | Land-cover class counts (`raster_alignment.py:900`) | Tile | part of the cold cost | The layer | Yes | To verify |
| F2a | Land-cover mosaic (`raster_alignment.py:987`) | Tile | part of the cold cost | The layer | Yes | To verify |
| F2a | Vector layers (`vector_alignment.py`) | Layer | short | Layer | No | Cache by key |
| F2b siting_layers | 14 layers | Layer | 58 s | Layer | No | Cache by key |
| F3 land_eligibility | Stripes of whole cell rows per technology and scenario (`windows.py`, `pipeline.py:648-935`, scratch `stripes_tmp`) | Stripe (about 1,000,000 pixels) | 1,117 s (6 technology-scenario runs, about 190 s each) | The phase, or one technology-scenario | Phase is 19 min; whether each technology-scenario output is cached separately is to verify | To verify |
| F4 climate_forcing | Forcing by member | Member (`members.py`) | 112 s | Phase | No | Below the limit |
| F4 hazard_context, climate_maps | Hazard summaries, maps | Member; map | 157 s; 80 s | Phase | No | Below the limit |
| overview | Diagnostic figures | Figure | 32 s | Phase | No | Below the limit |
| F5 technical_potential | Potential per technology and scenario, `cf_table` | Technology-scenario | 230 s | Phase | No (under 5 min); the CF table is already atomic | Below the limit |
| F5 potential_maps | Maps | Map | 41 s | Phase | No | Below the limit |
| F6 lcoe_modeling | LCOE members (`pipeline.py:324`, `TableWriter` streaming to `lcoe_summary_*.parquet`, `supply_curve_*.parquet`) | Member; block of cells (`max_batch_gb`) | Not measured | The whole table, because the writer streams into one `.partial` | Likely yes (sample 500 or more, members of the ensemble) | Verified: not resumable as written |
| F6 | Sample-size convergence (D-F6-004) | Sample size (doubling) | Not measured | The doubling step | Likely yes | To verify |
| F7 robustness_analysis | `evaluate` over blocks of cells; sample-major `futures_pass`; PRIM; bootstrap | Block of cells; batch of draws; scenario and window | Not measured | The pass | Likely yes | Verified structure (`pipeline.py:870-940`); random streams to verify |
| F7b external_validation | Inventory and enrichment | Table | Not measured | Phase | Likely no | To verify |
| F8 results_synthesis | Figures and tables | Figure; table | Not measured | Phase | Likely no | To verify |
| Figures (all phases) | `viz/`, `*figures.py` | Figure | seconds each | A figure | No | Atomic write to verify |

## 4. Writes that a power loss can corrupt (step 4 of the command)

These are findings independent of the checkpoint utility. Section 4 items 1 and 2 can produce a wrong result that looks valid, so they matter even without the new feature.

1. `core/raster_io.py:94-111` (`_write_cog`): deletes the final raster (`final_path.unlink()`) and then converts into it in place. A stop during the conversion leaves a truncated final file with no `.tmp`. If the sidecar key of an earlier run is still there and the inputs did not change, `cache_is_current` (`core/cache_key.py:105`) says the output is current. Fix: convert to a temporary name in the same directory, `fsync`, `os.replace`.
2. `core/cache_key.py:115` (`write_cache_key`) and `core/geo_utils.py:803`: `write_text` in place. A truncated key never matches (safe), but the order of writing output then key must be fixed and the key must be written atomically.
3. `core/tables.py:149` (`TableWriter.close`): `.partial` replaced without `fsync`. After a power loss NTFS can keep the renamed file with zero or partial data.
4. `core/orchestrator.py:826-832` (manifest), `core/reference_store.py`, `core/deferred_check.py`, `core/layer_process.py:184` (ledger), `core/code_fingerprint.py:305`, `core/clipped_cache.py:83`, `core/geo_utils.py:413`, `technical_potential/cf_table.py:102`: `.tmp` + `replace` is correct against a killed process; none flushes to disk first. Same power-loss exposure as item 3.
5. `core/artifact_json.py:68`, `core/cache_key.py:64` (hash memo): in-place writes; the memo already tolerates an unreadable file.
6. `RasterStream` (`core/raster_io.py:168`) discards the partial on an exception but not on a process kill: `*.writing.tif` files of 0 bytes remain (seen under `outputs/IND/grid_alignment/artifacts/` after the 2026-11-05 stop). Harmless to results, but the checkpoint utility must clean or reuse them.

## 5. Isolation of the units: can each be separated without changing the result?

- F2a elevation, slope and bins: yes. Each output block is a function of its own rows only (sums and counts per pixel, same order within the block). The block is the checkpoint unit.
- F6: the Latin hypercube samples come from one seed (`experiments.yaml`, `sampler.seed: 42`), so any member or block is a deterministic slice. To confirm in step 1: samples must be generated before the block loop (not drawn inside it from a running generator).
- F7: `evaluate` is block-wise on cells; `futures_pass` is sample-major in batches; the bootstrap and PRIM use seeds derived from the sampler seed (`experiments.yaml` line 455). Any step that draws from a single running random stream across units would not be isolable without changing the result. That is the stop-and-report condition of the command and is checked in step 1 per stage, before code.
- F3: stripes are documented as changing no result (`pipeline.py:801`, "sets the height of a stripe, that is the memory, and changes no result"), so a stripe is isolable. Cell sums across stripe boundaries and the final invariants (`_check_invariants`) must be computed after all stripes are present.

No unit has been found so far that cannot be isolated; the F6 and F7 random streams are the open risk.

## 6. Consequences for the plan

1. The utility `core/checkpoint.py` must serve three shapes of unit: a block of raster rows (F2a, F3 stripes), a parquet piece (F6 members and blocks, F7 blocks), and a file download (Range or whole file with hash). The common part is atomic write with `fsync`, the validity key, and cleanup.
2. The fix of section 4 items 1 to 4 is a prerequisite and should land first as `core/atomic_io.py`, used by the checkpoint utility and by every writer above.
3. F4, F5, overview, potential_maps and figures are each under 5 minutes in the BRA and rely on the layer cache, as the command allows.
4. F6, F7 and F8 need one measured run (the ZZZ synthetic world gives relative cost only) before the exact unit size is fixed. If the first real run is the one after this command, the checkpoint unit should be sized by time (flush about every 2 minutes), not by a fixed block count.

## 7. Open points to verify in step 1 (code reading, no change)

- F1b tile audit: per-tile results and whether they can be stored as pieces.
- F2a land-cover counts and mosaic: per-tile accumulation order.
- WorldCover and CMIP6 fetchers: `.part` handling, completeness check.
- F3: separate cache per technology-scenario or per phase.
- F6 and F7: where the random draws are generated relative to the member and block loops.
- F6 sample-size convergence: one output per size or one at the end.
- `run_unattended.ps1`: how a relaunch without flags decides what is incomplete (step 5).

## 8. Result of the implementation (2026-11-05)

Written after the work. Section 3 above is the inventory from before it; this section says what was done and what was not.

| Phase and layer | Unit stored | Where | Test (interruption compared with the continuous run) |
|---|---|---|---|
| F2a elevation, slope, slope bins | 32 rows of the grid (about 45 s on IND, about 110 s on BRA) | `grid_alignment/raster_alignment.py` `glo30_aligned_outputs`; dir `glo30_ckpt` | `test_checkpoint.py` (in the middle, twice in a row, cut unit, cut manifest, other key): rasters equal byte by byte |
| F2a land-cover counts | tile | `land_cover_class_counts`; dir `land_cover_counts_ckpt` | same file: counts resume to the continuous raster |
| F2a land-cover mosaic | tile (the part of the mosaic it gave) | `mosaic_land_cover`; dir `land_cover_ckpt` | same file: the first tile still wins; another tile order drops the checkpoint |
| F3 shares: lakes, protected areas, river corridors, settlement setbacks | strip of 40 rows | `land_eligibility/fractions.py`, `pipeline._fraction_files`; dir `<share>_ckpt` | `test_checkpoint.py`: strips resume to the same shares; the cache is whole after the restart |
| F6 LCOE | member (summary, supply curve, below curve, totals) | `lcoe_modeling/pipeline.py`; dir `<tech>_ckpt` | `test_lcoe_pipeline.py`: tables equal by content hash; no input read when every member is stored |
| F7 evaluation | member (running totals) | `robustness_analysis/evaluator.py` | `test_checkpoint_f7.py` |
| F7 sample-major pass | batch of draws | `robustness_analysis/futures.py` | same |
| F7 PRIM bootstrap | batch of 10 replicates, with `rng.bit_generator.state` | `robustness_analysis/scenario_discovery.py` | same; a control shows that without the restored state the table differs |
| F1 DEM and WorldCover tiles | `.part` continued with `Range`; a tile at its name is checked against the manifest (size, SHA-256) or probed | `core/resumable_download.py` | `test_resumable_download.py` (local HTTP server) |

Question of section 5 (a unit that cannot be isolated without changing the result): none was found. The F7 bootstrap draws from one generator; its state is stored with each batch, which keeps the stream, as decided on 2026-11-05.

### Not protected inside the unit

- **F1b vector clips** (IND `protected` 31 to 37 min, `roads` 21 min cold): declined, option A, `LIMITATIONS.md` L-063.
- **F3 first scenario of a country**: BRA takes about 7 minutes before the first scenario is written even with the shares cached; 19 s of that is the slope bins, the rest was not profiled (the six scenarios then take 18 to 45 s each). A stop in that stretch loses it.
- **GWA, ERA5 and CMIP6 downloads**: written to their own `.part` name and renamed (atomic against a killed process) but not flushed; `wind.py`, `era5.py` and `cmip6.py` (and `gadm.py`, through `wind.py`) are in the closure of the caches `gwa_mask_mosaic` and `era5_reduction`, so editing them would change those keys and rebuild them. The WDPA crawl (`protected_planet.py`) restarts from page 1; its final file is written whole or not at all.
- **Small JSON and text side files** (cache records of the audit, display metadata, the grid metadata, about 30 `write_text` calls) are written in place. A reader treats an unreadable one as stale, and `verify_cache_integrity.py` parses the state files; the manifest artifacts are written atomically by `main.py`.
- **`geo_utils.write_clip_cache_key`, `clipped_cache`, `cf_table`**: `.tmp` plus rename without flush; in the closure of the `clip` and `cf_table` caches.
- **F4, F5, overview, F7b, F8 and the figures**: each under 5 minutes on BRA (F5 230 s) or not measured; they rely on the layer cache.
- F6, F7 and F8 have not run on a real country: the units were sized from the structure of the code, not from a measured duration.

### Fingerprints after the change

Computed on the committed tree (HEAD, `9dd49df`) and on the working tree, each with its own code. Of the 40 fingerprints (19 phases, 9 closure caches, 12 aligned layers), **29 change and 11 do not**:

- Changed: the 12 aligned layers of F2a (`raster_io` and `tables` call the new write modules, and `glo30_aligned_outputs`, `land_cover_class_counts` and `mosaic_land_cover` take a checkpoint), the `subpixel_shares` cache (`fractions.py`, the strips) and 16 phases.
- Unchanged: the caches `clip`, `land_cover_tiles`, `raster_audit`, `dem30_extremes`, `era5_reduction`, `gwa_mask_mosaic`, `gadm_mainland` and `cf_table`, and the phases `data_quality_audit`, `external_inputs` and `overview`.
- `gadm.py` was edited at first (the zip written whole or not at all) and put back: it is in the closure of `gwa_mask_mosaic`, whose rebuild (IND, about 15 minutes) was not worth a zip of a few MB. The GADM zip is therefore still written in place (it is read back through `_safe_extract`, which refuses a cut zip).
- The `subpixel_shares` change rebuilds the shares of F3 in the next round. For IND and BRA the corridor and setback shares of Group 6 do not exist yet (they are built cold in that round, now with strip checkpoints); the lake and protected-area shares were made under the code of before COMMAND 97, which also changed `fractions.py`.
- The aligned layers are adopted once, at the end, under D-core-044 (section 9).
