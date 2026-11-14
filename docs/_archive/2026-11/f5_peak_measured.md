# Measured memory of F5 (`technical_potential`) on BRA, step by step (COMMAND 122, item 4)

Written for: the author, to decide where the memory of F5 goes before anything is changed. Read-only: no production code was edited, no official output was written (hashes of `outputs/BRA/manifest.json` and `references/latest.json` identical before and after, no file of `outputs/BRA`, `interim/BRA` or `references` modified). No code is proposed here. It closes the first open point of `docs/_audit/f5_peak_map.md`.

## Method

- **Where it ran.** A scratch data directory `GeoFREA_data/work/f5_122_<run>` with a copy of `outputs/BRA` (the round 1d34ab23, manifest included) and of `interim/BRA`, and `raw` and `external` as read-only junctions to the real ones (removed afterwards). `GEOFREA_DATA_DIR` pointed at it. The first attempt without `interim` recomputed "30 m DEM extremes" (817 tiles) inside the phase and was discarded: the official round had that cache.
- **What ran.** `main.py BRA --phases ... --rerun ...` (the real orchestrator, `technical_potential_run`, solar and wind in the one process, as in the round), in a **new process** each time, under a wrapper kept outside the repository. The wrapper rebinds names in the namespace of `geofrea.technical_potential.pipeline` in memory (`pd.read_parquet`, `pd.concat`, `read_cell_pixels`, `write_table`, `validate_candidates`, `assert_forcing_usable`, `_wind_input_flags`, `aggregate_scenario`, `model.prepare`, `model.prepare_pixels`, `build_technology_potential`) so that each call writes a mark (time, resident set, `peak_wset`), and a thread samples the resident set every 20 ms. The code on disk is untouched.
- **Metric.** Resident set of the process in MB (1 MB = 2^20 bytes), the same quantity as `peak_rss_mb` of the manifest (`core/peak_memory.py`). *Before* and *after* are the values at the two marks; *peak in step* is the highest sample between them, so it is a lower bound (a spike shorter than 20 ms can be missed; where the operating system peak is higher it is given in the text). Memory of child processes is not counted. Each run was made once: the run-to-run spread is not known (F3 had 1,305 MB in run c and 1,480 MB in the official round with the same code).
- **Run b** (`--phases technical_potential`): F5 alone in a new process, nothing from earlier phases in the heap. Phase peak in its manifest: **2,307 MB**, 253 s.
- **Run c** (`--phases land_eligibility,technical_potential`): F3 first and F5 right after, in the same process, as in the round. F5 peak **2,585 MB**, 231 s; F3 1,305 MB.
- **Official round** (manifest, 2026-11-09): `grid_alignment`, `siting_layers`, `land_eligibility`, `technical_potential` and `potential_maps` ran one after the other in one process (each starts in the second the previous one ends). F5: **3,410 MB**, 236 s.

## Result

| run | what was in the process before F5 | RSS when F5 starts | F5 peak |
|---|---|---:|---:|
| b | nothing | 247 | 2,307 |
| c | F3 | 732 | 2,585 |
| official | grid_alignment, siting_layers, F3 (peaks 437, 272, 1,480) | not recorded | 3,410 |

(RSS when F5 starts: the value at the first `build_technology_potential` mark. In run c, the row "setup" of the tables below is F3 plus the setup and its peak is the sampled peak of F3.)

### Solar (37 members), RSS in MB; run b, with the sampled peak of run c beside it

Setup before the first technology: run b 135 to 247, sampled peak 435 (44 s: imports, configuration, country geometry, input ranges); run c 135 to 732, sampled peak 1,215 (it includes F3).

| step | RSS before | RSS after | peak in step | peak in step, run c |
|---|---:|---:|---:|---:|
| read `forcing.parquet` (10.58 M rows) | 247 | 766 | 766 | 929 |
| `forcing['member'].astype(str)` | 766 | 1,094 | 1,971 | 2,446 |
| read `forcing_masked.parquet` | 1,094 | 563 | 1,100 | 1,566 |
| `set(forcing['member'])` check and `warn_unranged` (no marked call) | 563 | 563 | 563 | 1,150 |
| 3 scenarios: read candidates, `validate_candidates`, `assert_forcing_usable` | 563 | 1,078 | 1,719 | 2,077 |
| `by_member`: `groupby('member')` + `set_index('cell_id')` x member | 1,078 | 1,084 | 1,375 | 1,701 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), central | 1,086 | 1,385 | 1,385 | 1,727 |
| `pd.concat(pieces)`, central | 1,385 | 1,607 | 1,607 | 1,947 |
| `write_table` potential (zstd), central | 1,608 | 1,630 | 1,633 | 1,973 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), restrictive | 1,635 | 1,619 | 1,635 | 1,959 |
| `pd.concat(pieces)`, restrictive | 1,619 | 1,839 | 1,839 | 2,167 |
| `write_table` potential (zstd), restrictive | 1,617 | 1,622 | 1,645 | 1,971 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), permissive | 1,627 | 1,634 | 1,647 | 1,962 |
| `pd.concat(pieces)`, permissive | 1,634 | 1,867 | 1,867 | 2,193 |
| `write_table` potential (zstd), permissive | 1,647 | 1,639 | 1,675 | 1,999 |
| `write_table` aggregates, return of `build_technology_potential` (locals freed) | 1,659 | 823 | 1,659 | 1,985 |

### Wind (31 members), same columns

| step | RSS before | RSS after | peak in step | peak in step, run c |
|---|---:|---:|---:|---:|
| read `forcing.parquet` (10.58 M rows) | 824 | 612 | 856 | 1,255 |
| `forcing['member'].astype(str)` | 612 | 1,243 | 2,137 | 2,444 |
| read `forcing_masked.parquet` | 1,243 | 696 | 1,243 | 1,564 |
| `set(forcing['member'])` check and `warn_unranged` (no marked call) | 696 | 696 | 696 | 1,012 |
| 3 scenarios: read candidates, `validate_candidates`, `assert_forcing_usable` | 696 | 1,042 | 1,707 | 2,026 |
| `by_member`: `groupby('member')` + `set_index('cell_id')` x member | 1,042 | 1,084 | 1,342 | 1,674 |
| `read_cell_pixels`, central | 1,084 | 1,355 | 1,667 | 1,989 |
| `prepare_pixels`, central | 1,361 | 1,450 | 1,523 | 1,834 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), central | 1,211 | 1,455 | 1,570 | 1,861 |
| `pd.concat(pieces)`, central | 1,455 | 1,628 | 1,628 | 1,918 |
| `write_table` potential (zstd), central | 1,628 | 1,654 | 1,656 | 1,939 |
| `read_cell_pixels`, restrictive | 1,656 | 1,892 | 2,172 | 2,458 |
| `prepare_pixels`, restrictive | 1,896 | 1,968 | 2,014 | 2,266 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), restrictive | 1,640 | 1,601 | 1,716 | 1,988 |
| `pd.concat(pieces)`, restrictive | 1,601 | 1,756 | 1,756 | 2,026 |
| `write_table` potential (zstd), restrictive | 1,582 | 1,593 | 1,609 | 1,881 |
| `read_cell_pixels`, permissive | 1,597 | 1,914 | 2,244 | 2,556 |
| `prepare_pixels`, permissive | 1,920 | 2,017 | 2,066 | 2,342 |
| per-member loop (`prepared.member`, `annual_energy_mwh`, 37 or 31 frames), permissive | 1,628 | 1,668 | 1,790 | 2,057 |
| `pd.concat(pieces)`, permissive | 1,668 | 1,863 | 1,863 | 2,134 |
| `write_table` potential (zstd), permissive | 1,709 | 1,724 | 1,735 | 2,010 |
| `write_table` aggregates, return of `build_technology_potential` (locals freed) | 1,723 | 882 | 1,723 | 1,997 |

After the wind technology returns the process goes to 247 MB (run b; 882 before), against 247 MB before the solar one began.

## Where the peak is

- **The peak of F5 is `read_cell_pixels` of the third wind scenario (permissive):** the highest sample is 2,244 MB in run b (the operating system recorded 2,307 MB for the phase, a spike the sampler did not see) and 2,556 in run c (2,585 recorded). The step adds about 0.65 GB over the 1.6 GB that the process already holds when it starts.
- **The solar peak** is 1,867 MB (run b) at the `pd.concat` of the third scenario, 2,193 in run c.
- **Before the loops, the largest transient is `forcing['member'].astype(str)`:** 1,971 MB solar and 2,137 MB wind in run b (2,446 in run c) from a floor of 766 and 612. It is a spike of about 1.2 to 1.5 GB that the map did not have as an item (it counted "about 300 MB in pandas with member turned to strings"); from the code, it is the dictionary column of 10.58 M rows turned into Python strings, and it is gone one call later. It is the peak of the phase until the wind loop begins, and in run b it is within 0.1 GB of the highest point of the phase (2,137 against 2,244 MB), but it does not set it.
- **`by_member` is cheap:** +6 and +42 MB net, a transient of 0.3 GB. The 0.6 GB "held" of the map was `forcing` plus `by_member`; the forcing is already 0.5 GB after the read and `by_member` adds little.
- **The loop between scenarios keeps what the previous scenario made.** The process holds 1,084 MB before the first wind scenario and 1,656 and 1,597 MB before the second and third: **about 0.55 GB more**, with `forcing` and `by_member` unchanged. By the code (not by an object-size measurement) this is what the previous scenario leaves bound until the next one rebinds it: the list `pieces` (31 or 37 frames), the concatenated `table`, and `prepared` (the pixel arrays). The map counted the `table` of that scenario as alive at that point, not the `pieces` and `prepared` that stay with it. The same 0.5 GB step appears in solar (1,084 to 1,635).
- **Between the two technologies the process does not come back:** 823 MB after solar and 882 MB after wind, against 247 MB before the first one (about 0.6 GB retained by the heap, `pyarrow` and `pandas`).
- **Wall time** is the same in the three runs (231 to 253 s); the per-member loop of wind (25 to 33 s per scenario) and, in each technology, the 15 s between the read of `forcing_masked.parquet` and the first candidates table (no change of memory; from the code it is the check `set(forcing['member'])` and `warn_unranged`) are the long steps.

## Where the 1.4 GB the map did not explain are

The map added about 2.0 GB at the top (0.3 process + 0.6 forcing and `by_member` + 0.1 candidates + 1.0 `read_cell_pixels`) against 3,410 MB measured, a gap of about 1.4 GB. Measured:

| part | MB | status |
|---|---:|---|
| Arithmetic of the map, wind permissive, at the top | about 2,000 | map |
| F5 alone in a new process (run b, 2,307) minus the arithmetic | about +300 | **located**: the process holds 1.6 GB, not 1.0 GB, when the third wind scenario reads its pixels (about 0.5 GB of it is what the previous scenario leaves bound, `pieces`, `table`, `prepared`), and `read_cell_pixels` adds 0.65 GB, less than the 1.0 GB of the map |
| F3 run before F5 in the same process (run c, 2,585) minus run b | +278 (+485 at the start of F5: 732 against 247) | **located**: measured |
| Official round (3,410) minus run c | about +825 | **not located** |
| Total | about 1,410 | 0.6 GB located, 0.8 GB not |

What this run **does not** show, and could be the 0.8 GB (none of it tested): the official process also ran `grid_alignment` (604 s, manifest peak 437 MB) and `siting_layers` (98 s, 272 MB) before F3, and run c did not; the run-to-run variation (F3 alone differs by 175 MB between the round and run c); and anything else the round process held that a manifest does not record (OQ-068, `docs/_audit/f3_peak_118.md`). Only a run of the whole chain from `grid_alignment` in one process, with the wrapper, would say which. The memory of the phase is, in the measurement, 2.3 GB when it runs alone and 2.6 GB after F3: over the cap of 1,536 MB (`docs/_audit/memory_budget_88.md`) in both cases, with or without the unexplained part.

## What the measurement does not cover

- `potential_maps` and the later phases were not measured. Only F5, on BRA.
- IND and PRT were not measured; the table is BRA.
- Each configuration ran once.
- The marks are at the calls the wrapper could rebind; inside the per-member loop and inside `read_cell_pixels` the memory is read as a time series, not by line.
