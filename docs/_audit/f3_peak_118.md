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

## Conclusion and what would settle it

The cause is **not determined**. What is established: same code, same configuration, same work (CPU), a higher process-wide peak, and a margin of 55 MB under the 1,536 MB cap. What is not: whether the +238 MB belongs to F3 or to the process around it.

Two measurements, neither run (both rerun F3 of BRA, about 10 minutes, and write its outputs): F3 alone in a fresh process on the current inputs, and the same on the inputs of the snapshot of 9c2dc3c8 (`work/pre116/BRA`). If the peak of F3 alone is the same (about 1,240 MB) on both, the rise is the process around it; if it differs between the two inputs, it is the data. They need the author's authorization because the second one overwrites the current outputs of BRA unless it is pointed at a scratch directory.
