# Why the F3 peak of BRA was 1,481 MB in the round 1d34ab23 and 1,243 MB in the round 9c2dc3c8 (COMMAND 118, item 4)

Written for: the author. Read-only investigation: no code was run again and none was changed. Sources: the manifests of the two rounds (`references/9c2dc3c8.../BRA/manifest.json` and `outputs/BRA/manifest.json`), `config/memory_budget.json`, `core/peak_memory.py`, `git log` of `src/geofrea/land_eligibility`.

## What is measured, and the numbers

`peak_rss_mb` of a phase is the highest working set **of the whole Python process** while the phase ran (`core/peak_memory.py`: the OS peak when the phase raised it, otherwise the maximum sampled every 0.25 s). It is not the memory of the phase alone: whatever the earlier phases of the same process left resident counts.

| | round 9c2dc3c8 (2026-11-07) | round 1d34ab23 (2026-11-09) |
|---|---|---|
| `land_eligibility` peak | 1,243 MB | 1,481 MB (+238) |
| `land_eligibility` wall / CPU | 578 s / 538 s | 602 s / 550 s (+4 % / +2 %) |
| code fingerprint of the phase | 20835176 | 20835176 (same) |
| config fingerprint of the phase | f85925b1 | f85925b1 (same) |
| `siting_layers` peak | 888 MB | 272 MB |
| `technical_potential` peak | 2,829 MB | 3,410 MB |
| `potential_maps` peak | 1,898 MB | 2,548 MB |

`config/memory_budget.json` holds three F3 values for BRA: `f3_phase` 1,438 MB (COMMAND 91, 2026-11-04, profile harness and a pipeline run), `f3_phase_fabdem_round` 1,243 MB (the round 9c2dc3c8) and, since COMMAND 116, `f3_phase_distance_round` 1,481 MB. The decision ceiling stated there is the larger value.

## What changed in F3 since 9c2dc3c8

Nothing that the code fingerprint sees. The fingerprint of `land_eligibility` is identical before and after, and so is its configuration fingerprint. The only edits to `src/geofrea/land_eligibility` after the round are comments of lint suppressions (commit `26ccb43`, `cells.py`, two lines), which do not change the normalised tree. The change of COMMANDS 115 to 117 is in `grid_alignment` (distance layers) and reaches F3 only through the **content** of the three distance rasters it reads (`dist_grid_km`, `dist_road_km`, `dist_sub_km`): the same shape and dtype, different values. The size of the stripes of F3 is a constant (`_STRIPE_PIXELS` = 4,000,000 pixels in `cells.py`, the windows of `windows.py`): it does not adapt to the free memory, so a different amount of free memory does not change how F3 reads.

## Hypotheses and what the evidence says

1. **Not the code and not the configuration.** Same fingerprints, wall and CPU within a few percent: the same work was done.
2. **State of the process when F3 starts (the measure is process-wide).** In the round 1d34ab23 `main.py` ran data_acquisition (271 s), data_quality_audit (161 s), grid_alignment (604 s), climate_forcing (111 s) and siting_layers in the same process before F3 (the manifest of the round 9c2dc3c8 does not say which phases were executed and which resumed in its process); what each left resident (Python heap not returned to the OS, caches) adds to the peak of every later phase. This fits that the three phases after the first of them rose (F3 +238, F5 +581, potential_maps +650 MB), but **it does not explain `siting_layers`, which fell from 888 to 272 MB** in the same comparison, so the composition of the process before F3 differed between the rounds in a way the manifests do not record (which phases were resumed from their manifest entry and which executed).
3. **Content of the distance rasters.** The new distances are real numbers where the old ones were multiples of one scale (and exact zeros at the burnt pixels); the compression of the rasters read by windows and the number of distinct values in the output tables differ. The tables have 286,043 rows, the output rasters are written by stripes: no arithmetic here accounts for +238 MB, so this is a weak hypothesis.
4. **The machine at the time.** Round 1d34ab23 ran with VS Code open (the session of Claude Code runs in it), the round 9c2dc3c8 is recorded in `config/memory_budget.json` as the peak of the unattended runner (`run_unattended.ps1`, which asks for VS Code and the browser closed); that this was how it ran is taken from that note, not checked. Windows trims the working set of a process under memory pressure, which lowers a measured working-set peak, and changes how much of the freed heap stays resident. The direction of the effect is not known and the free memory during F3 was not recorded in this round, and it was not looked for in the files of the earlier one.

## Measurement (COMMAND 119, item 4): F3 of BRA alone, in a new process

Run in scratch directories outside the official outputs (`GEOFREA_DATA_DIR` pointed at a copy of `outputs/BRA` and `interim/BRA`; `raw` and `external` joined by junctions, removed afterwards; no official output was written, the manifest of `outputs/BRA` kept its date). `main.py BRA --phases land_eligibility --rerun land_eligibility`: every phase upstream resumed from its manifest entry, only `land_eligibility` executed, so the process held nothing but F3.

| inputs | peak | wall | CPU |
|---|---|---|---|
| current (round 1d34ab23: exact distances) | **1,363 MB** | 662 s | 581 s |
| of 9c2dc3c8 (snapshot `work/pre116/BRA`: isotropic distances) | **1,376 MB** | 639 s | 574 s |

For the second run the manifest copy of the scratch directory had the code fingerprint of `grid_alignment` set to the current one (otherwise the orchestrator executes `grid_alignment` again and replaces the old rasters); the old `dist_sub_km.tif` was confirmed unchanged by hash (50e4ee1f6781 in the snapshot and in the scratch directory, 6155eb13d8c3 in the current outputs). Two earlier attempts of this run failed on the command line (`--revalidate` accepts only a `stale_upstream` entry) and a third started `grid_alignment` and was stopped; none left output.

## What it settles

- **The data (hypothesis 3) is rejected:** the old and the new distances give 1,376 and 1,363 MB, 13 MB apart, with the same code and the same work.
- **The process around F3 (hypothesis 2) accounts for part of it:** F3 inside the round peaked at 1,481 MB, alone at 1,363 MB: **about 118 MB** is what the earlier phases of the same process left resident.
- **What is not explained:** F3 alone peaks at about 1,370 MB now, against the 1,243 MB recorded for the round 9c2dc3c8 for the same code fingerprint (20835176) and the same configuration: **about 120 to 130 MB** that neither the inputs nor the process around account for. What is left: the state of the share caches in `interim/BRA/land_eligibility` (the profile of COMMAND 91 measured 1,260 MB with them current and 1,218 with them rebuilt, a 40 MB spread), the versions of the libraries (pandas, pyarrow, rasterio, numpy) on the machine on 2026-11-07 against today (not compared), and the way the peak of the round 9c2dc3c8 was taken. None of the three was investigated.
- **For the budget:** F3 of BRA is 1,363 to 1,376 MB alone and 1,481 MB inside a run that executes the earlier phases first: 55 MB under the cap in the second case, 160 MB in the first. The `f3_phase` ceiling of 1,438 MB is passed only in the in-run case.
